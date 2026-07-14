from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from invoice_agent.db.models import Job, LedgerEntry
from invoice_agent.schema import Invoice


async def create_job(
    session: AsyncSession, file_key: str, ledger_entry_id: int | None = None
) -> Job:
    job = Job(ledger_entry_id=ledger_entry_id, file_key=file_key)
    session.add(job)
    await session.commit()
    return job


async def write_invoice(
    session: AsyncSession,
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
    session.add(entry)
    await session.commit()
    return entry


async def find_duplicate(
    session: AsyncSession, invoice_number: str | None, vendor_name: str | None
) -> LedgerEntry | None:
    if invoice_number is None or vendor_name is None:
        return None

    statement = select(LedgerEntry).where(
        LedgerEntry.invoice_number == invoice_number,
        LedgerEntry.vendor_name == vendor_name,
    )
    result = await session.exec(statement)
    return result.first()
