from sqlmodel import Session
from invoice_agent.db.models import LedgerEntry
from invoice_agent.schema import Invoice


def write_invoice(
    engine,
    invoice: Invoice,
    needs_review: bool = False,
    review_reason: str | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor.name if invoice.vendor else None,
        issue_date=invoice.issue_date,
        currency=invoice.currency,
        grand_total=invoice.grand_total,
        invoice_data=invoice.model_dump(mode="json"),
        needs_review=needs_review,
        review_reason=review_reason,
    )
    with Session(engine) as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
    return entry
