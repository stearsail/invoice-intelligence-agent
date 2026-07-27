import asyncio
from dataclasses import dataclass
import logging
from invoice_agent.agent.error_categories import categorize_error
from invoice_agent.agent.images import load_image_b64
from invoice_agent.schema import Invoice
from langchain_anthropic import ChatAnthropic
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    invoice: Invoice | None
    parse_error: str | None


class SpecialistExtractor:
    def __init__(
        self, base_url: str, api_key: str, model_name: str = "qwen3-vl-fullds-merged-r8"
    ):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model_name = model_name

    # TODO: replace manual JSON parsing with vLLM guided decoding
    # (extra_body={"guided_json": ...}), which constrains generation to the
    # schema during decoding instead of validating after the fact.
    #
    # Invoice.model_json_schema() can't be passed directly: Pydantic renders
    # Decimal fields with a negative-lookahead pattern, which grammar backends
    # compile to automata and can't express. Needs a separate wire schema with
    # money as plain strings (parsed via the CORD price parser, which keeps
    # locale info that a JSON number would destroy — "45.000" is 45000 IDR).
    # Enums and simple regex (^[A-Z]{3}$, ISO dates) do compile and are worth
    # keeping; "format": "date" is not enforced, so parsing stays.
    #
    # Measure the malformed-output rate first — the specialist is fine-tuned on
    # this format, so the gain may not justify the second schema.
    async def extract_invoice(self, img_path: str) -> ExtractionResult:
        response = None
        try:
            img_b64, mime_type = await asyncio.to_thread(load_image_b64, img_path)
            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract structured data from this receipt/invoice image as JSON.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{img_b64}"
                                },
                            },
                        ],
                    }
                ],
            )
            return ExtractionResult(
                invoice=Invoice.model_validate_json(
                    response.choices[0].message.content
                ),
                parse_error=None,
            )
        except Exception as e:
            category = categorize_error(e)
            if category == "connectivity":
                raise
            if response is not None:
                logger.warning(
                    "Extraction parse failure (%s): raw=%r",
                    category,
                    response.choices[0].message.content[:2000],
                )
            return ExtractionResult(invoice=None, parse_error=f"{category}: {e}")


class FrontierExtractor:
    def __init__(
        self, model_name: str, temperature: float = 0.1, max_tokens: int = 4096
    ):
        self._client = ChatAnthropic(
            model=model_name,
            temperature=temperature,
            max_tokens_to_sample=max_tokens,
            max_retries=0,
        )

    async def extract_invoice(
        self, img_path: str, extra_context: str = ""
    ) -> ExtractionResult:
        try:
            img_b64, mime_type = await asyncio.to_thread(load_image_b64, img_path)
            message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Extract structured data from this receipt/invoice image as JSON. 
                        Read the currency, number formatting, and locale directly from what's visible in the document 
                        — do not assume any specific country's conventions."""
                        + extra_context,
                    },
                    {
                        "type": "image",
                        "base64": img_b64,
                        "mime_type": mime_type,
                    },
                ],
            }
            structured_model = self._client.with_structured_output(
                Invoice, include_raw=True
            )
            result = await structured_model.ainvoke([message])
        except Exception as e:
            category = categorize_error(e)
            if category == "connectivity":
                raise
            return ExtractionResult(invoice=None, parse_error=f"{category}: {e}")
        if result["parsing_error"] is not None:
            category = categorize_error(result["parsing_error"])
            raw_text = result["raw"].content if result.get("raw") else None
            logger.warning(
                "Extraction parse failure (unknown): raw=%r", str(raw_text)[:2000]
            )
            return ExtractionResult(
                invoice=None, parse_error=f"unknown:{result['parsing_error']}"
            )
        return ExtractionResult(invoice=result["parsed"], parse_error=None)
