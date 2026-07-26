from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from sqlmodel import JSON, SQLModel, Field, Column, String


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
    review_reason: list[dict] | None = Field(sa_column=Column(JSON))
    job_id: int = Field(foreign_key="job.id")


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    attempts: int = Field(default=1)
    status: Literal["pending", "complete", "extraction_failed", "error", "retrying"] = (
        Field(default="pending", sa_column=Column(String, nullable=False))
    )
    error: str | None = Field(default=None)
    file_key: str
