from typing_extensions import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from invoice_agent.schema import Invoice
from invoice_agent.reconciliation import reconcile
from invoice_agent.images import load_image_b64
from langchain_anthropic import ChatAnthropic
from openai import OpenAI
import os
import getpass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

if "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API Key: ")

model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0.1,
    max_tokens_to_sample=4096,
    max_retries=0,
)


class State(TypedDict):
    image: str
    invoice: Invoice
    parse_error: str | None
    reconciliation_issues: list[str]
    attempt: Literal["specialist", "frontier"]


class Context(TypedDict):
    model_name: str = "qwen3-vl-cord-merged"


# TODO: replace manual JSON parsing with vLLM's native structured-output /
# guided decoding (constrains generation to match the schema directly),
# once server-side config for it is set up. Would reduce the specialist's
# malformed-output rate.
def extract_invoice(state: State) -> dict:
    print("Running invoice information extraction")
    img_path = state["image"]
    img_b64 = load_image_b64(img_path)
    response = client.chat.completions.create(
        model="qwen3-vl-cord-merged",
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
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            }
        ],
    )
    invoice_str = response.choices[0].message.content
    try:
        invoice = Invoice.model_validate_json(invoice_str)
        return {"invoice": invoice, "parse_error": None, "attempt": "specialist"}
    except Exception as e:
        return {"parse_error": f"Pydantic Validation error: {e}"}


def _call_frontier(state: State, extra_context: str = "") -> dict:
    img_path = state["image"]
    img_b64 = load_image_b64(img_path)
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
                "mime_type": "image/png",
            },
        ],
    }

    structured_model = model.with_structured_output(Invoice)
    invoice = structured_model.invoke([message])
    return {"invoice": invoice, "attempt": "frontier"}


def frontier_extract_fallback(state: State) -> dict:
    return _call_frontier(state)


def frontier_review_fallback(state: State) -> dict:
    context = (
        f"Validation and reconciliation issues exist in the previous extraction "
        f"— take these into consideration: {state['reconciliation_issues']}"
    )
    return _call_frontier(state, extra_context=context)


def validate_reconcile(state: State) -> dict:
    issues = reconcile(state["invoice"])
    return {"reconciliation_issues": issues}


def route_after_parsing(state: State) -> str:
    if state["parse_error"] is None:
        return "success"
    return "needs_fallback"


def route_after_reconcile(state: State) -> str:
    if not state["reconciliation_issues"]:
        return "reconciled"
    elif state["attempt"] == "frontier":
        return "needs_human_review"
    return "needs_review"


builder = StateGraph(state_schema=State, context_schema=Context)
builder.add_node("extract_invoice", extract_invoice)
builder.add_node("frontier_extract_fallback", frontier_extract_fallback)
builder.add_node("validate_reconcile", validate_reconcile)
builder.add_node("frontier_review_fallback", frontier_review_fallback)

builder.add_edge(START, "extract_invoice")
builder.add_conditional_edges(
    "extract_invoice",
    route_after_parsing,
    {"success": "validate_reconcile", "needs_fallback": "frontier_extract_fallback"},
)
builder.add_edge("frontier_extract_fallback", "validate_reconcile")
builder.add_conditional_edges(
    "validate_reconcile",
    route_after_reconcile,
    {
        "needs_review": "frontier_review_fallback",
        "reconciled": END,
        "needs_human_review": END,
    },
)
builder.add_edge("frontier_review_fallback", "validate_reconcile")
graph = builder.compile()

if __name__ == "__main__":
    result = graph.invoke(
        {"image": "data/processed/CORD/images/test/99.png", "invoice": None}
    )
