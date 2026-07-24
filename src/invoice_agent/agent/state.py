from typing_extensions import Literal, TypedDict
from invoice_agent.schema import Invoice
from invoice_agent.reconciliation import ReconciliationIssue


class State(TypedDict):
    job_id: int
    image: str
    invoice: Invoice | None
    parse_error: str | None
    reconciliation_issues: list[ReconciliationIssue]
    attempt: Literal["specialist", "frontier"]
    ledger_entry_id: int


class Context(TypedDict):
    model_name: str = "qwen3-vl-fullds-merged-r8"
