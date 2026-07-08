import base64

from typing_extensions import Annotated, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.runtime import Runtime
from invoice_agent.schema import Invoice
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")


class State(TypedDict):
    image: str
    invoice: Invoice
    parse_error: str | None


class Context(TypedDict):
    model_name: str = "qwen3-vl-cord-merged"


def extract_invoice(state: State) -> None:
    print("Running invoice information extraction")
    img_path = state["image"]
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

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
        return {"invoice": invoice, "parse_error": None}
    except Exception as e:
        return {"parse_error": f"Pydantic Validation error: {e}"}


def route_after_parsing(state: State) -> str:
    if state["parse_error"] is None:
        return "success"
    return "needs_fallback"


def frontier_fallback(state: State) -> None:
    print("I'm the frontier model, I'll fix this up for you")
    


def no_fallback(state: State) -> None:
    print("No fallback was needed, let the frontier model chill")
    print(state["invoice"])


builder = StateGraph(state_schema=State, context_schema=Context)
builder.add_node("extract_invoice", extract_invoice)
builder.add_node("no_fallback", no_fallback)
builder.add_node("frontier_fallback", frontier_fallback)

builder.add_edge(START, "extract_invoice")
builder.add_conditional_edges(
    "extract_invoice",
    route_after_parsing,
    {"success": "no_fallback", "needs_fallback": "frontier_fallback"},
)
builder.add_edge("no_fallback", END)
builder.add_edge("frontier_fallback", END)
graph = builder.compile()

result = graph.invoke(
    {"image": "data/processed/CORD/images/test/0.png", "invoice": None}
)
