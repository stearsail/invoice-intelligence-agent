from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from invoice_agent.schema import Invoice
from invoice_agent.reconciliation import ReconciliationIssue


class JobCreationResponse(BaseModel):
    job_id: int
    status: str


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int | None
    invoice_number: str | None
    vendor_name: str | None
    issue_date: date | None
    currency: str
    grand_total: Decimal
    invoice_data: Invoice
    created_at: datetime
    needs_review: bool
    review_reason: list[ReconciliationIssue] | None


class PendingJobResponse(BaseModel):
    job_id: int
    created_at: datetime
    status: str
    attempts: int


class JobEntryPairResponse(BaseModel):
    job_id: int
    created_at: datetime
    status: str
    error: str | None
    attempts: int
    ledger_entry: LedgerEntryResponse | None
    ledger_entry_error: str | None = None
