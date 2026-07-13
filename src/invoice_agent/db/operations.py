from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.session import async_sessionmaker
from sqlmodel import select
from invoice_agent.db.models import LedgerEntry
from invoice_agent.schema import Invoice


async def write_invoice(
    async_session: async_sessionmaker[AsyncSession],
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
    async with async_session() as session:
        session.add(entry)
        await session.commit()
    return entry


async def find_duplicate(
    async_session: async_sessionmaker[AsyncSession],
    invoice_number: str | None,
    vendor_name: str | None,
) -> LedgerEntry | None:
    if invoice_number is None or vendor_name is None:
        return None

    statement = select(LedgerEntry).where(
        LedgerEntry.invoice_number == invoice_number,
        LedgerEntry.vendor_name == vendor_name,
    )
    async with async_session() as session:
        result = await session.exec(statement)
        return result.first()
