from datetime import date, datetime
from decimal import Decimal
from sqlmodel import JSON, SQLModel, Field, Column


class LedgerEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_number: str | None = Field(default=None, index=True)
    vendor_name: str | None = Field(default=None, index=True)
    issue_date: date | None = None
    currency: str
    grand_total: Decimal
    invoice_data: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    needs_review: bool = Field(default=False, index=True)
    review_reason: str | None = Field(default=None)
