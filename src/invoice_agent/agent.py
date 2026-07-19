import asyncio

from typing_extensions import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from invoice_agent.db.operations import find_duplicate, write_entry
from invoice_agent.schema import Invoice
from invoice_agent.reconciliation import ReconciliationIssue, reconcile
from invoice_agent.images import load_image_b64
from langchain_anthropic import ChatAnthropic
from openai import AsyncOpenAI
import os
import getpass
from pathlib import Path
from dotenv import load_dotenv
from invoice_agent.db.engine import session_factory

load_dotenv(Path(__file__).parent.parent.parent / ".env")

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="not-needed")

if "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API Key: ")

model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0.1,
    max_tokens_to_sample=4096,
    max_retries=0,
)


class State(TypedDict):
    job_id: int
    image: str
    invoice: Invoice | None
    parse_error: str | None
    reconciliation_issues: list[ReconciliationIssue]
    attempt: Literal["specialist", "frontier"]
    ledger_entry_id: int


class Context(TypedDict):
    model_name: str = "qwen3-vl-cord-merged"


# TODO: replace manual JSON parsing with vLLM's native structured-output /
# guided decoding (constrains generation to match the schema directly),
# once server-side config for it is set up. Would reduce the specialist's
# malformed-output rate.
async def extract_invoice(state: State) -> dict:
    img_path = state["image"]
    img_b64 = load_image_b64(img_path)
    response = await client.chat.completions.create(
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


async def _call_frontier(state: State, extra_context: str = "") -> dict:
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
    try:
        invoice = await structured_model.ainvoke([message])
        return {"invoice": invoice, "attempt": "frontier"}
    except Exception as e:
        return {
            "parse_error": f"Frontier structured output error: {e}",
            "attempt": "frontier",
        }


async def frontier_extract_fallback(state: State) -> dict:
    return await _call_frontier(state)


async def frontier_review_fallback(state: State) -> dict:
    context = (
        f"Validation and reconciliation issues exist in the previous extraction "
        f"— take these into consideration: {state['reconciliation_issues']}"
    )
    return await _call_frontier(state, extra_context=context)


async def validate_reconcile(state: State) -> dict:
    if state["invoice"] is None:
        return {
            "reconciliation_issues": [
                ReconciliationIssue(
                    category="unverifiable",
                    message="Extraction failed entirely — no invoice to reconcile",
                )
            ]
        }
    issues = reconcile(state["invoice"])

    vendor_name = state["invoice"].vendor.name if state["invoice"].vendor else None
    async with session_factory() as session:
        duplicate = await find_duplicate(
            session, state["invoice"].invoice_number, vendor_name
        )
    if duplicate is not None:
        issues.append(
            ReconciliationIssue(
                category="duplicate",
                message=f"Duplicate invoice # — '{state['invoice'].invoice_number}' already exists in ledger (Entry ID {duplicate.id})",
            )
        )
    return {"reconciliation_issues": issues}


def route_after_parsing(state: State) -> str:
    if state["parse_error"] is None:
        return "success"
    return "needs_fallback"


def route_after_reconcile(state: State) -> str:
    if state["invoice"] is None:
        return "total_failure"
    if not state["reconciliation_issues"]:
        return "reconciled"
    elif state["attempt"] == "frontier":
        return "needs_human_review"
    return "needs_review"


async def ledger_write(state: State) -> dict:
    needs_review = bool(state["reconciliation_issues"])
    review_reason = (
        [issue.model_dump() for issue in state["reconciliation_issues"]]
        if needs_review
        else None
    )
    async with session_factory() as session:
        entry = await write_entry(
            session,
            state["job_id"],
            state["invoice"],
            needs_review=needs_review,
            review_reason=review_reason,
        )
    return {"ledger_entry_id": entry.id}


builder = StateGraph(state_schema=State, context_schema=Context)
builder.add_node("extract_invoice", extract_invoice)
builder.add_node("frontier_extract_fallback", frontier_extract_fallback)
builder.add_node("validate_reconcile", validate_reconcile)
builder.add_node("frontier_review_fallback", frontier_review_fallback)
builder.add_node("ledger_write", ledger_write)

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
        "reconciled": "ledger_write",
        "needs_human_review": "ledger_write",
        "total_failure": END,
    },
)
builder.add_edge("frontier_review_fallback", "validate_reconcile")
builder.add_edge("ledger_write", END)
graph = builder.compile()

if __name__ == "__main__":
    result = asyncio.run(
        graph.ainvoke(
            {"image": "data/processed/CORD/images/test/99.png", "invoice": None}
        )
    )
