from typing import Literal
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class Party(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    address: str | None = None
    tax_id: str | None = None
    iban: str | None = None


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendor: Party | None = None
    customer: Party | None = None
    document_type: Literal["invoice", "receipt", "credit_note"]
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    line_items: list[LineItem] = Field(default_factory=list)
    grand_total: Decimal
    confidence_notes: list[str] = Field(default_factory=list)
