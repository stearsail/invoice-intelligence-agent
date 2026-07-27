from typing_extensions import Literal, TypedDict
from invoice_pipeline.schema import Invoice
from invoice_pipeline.reconciliation import ReconciliationIssue


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
