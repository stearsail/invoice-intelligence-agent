from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import or_, select
from invoice_agent.db.models import Job, LedgerEntry
from invoice_agent.schema import Invoice


async def create_job(
    session: AsyncSession, file_key: str, ledger_entry_id: int | None = None
) -> Job:
    job = Job(file_key=file_key)
    session.add(job)
    await session.commit()
    return job


async def update_job(
    session: AsyncSession,
    job_id: int,
    status_update: str,
    error_update: str | None = None,
) -> Job:
    job = await session.get(Job, job_id)
    job.status = status_update
    job.error = error_update
    session.add(job)
    await session.commit()
    return job


async def query_job(session: AsyncSession, job_id: int) -> Job:
    job = await session.get(Job, job_id)
    return job


async def write_entry(
    session: AsyncSession,
    job_id: int,
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
        job_id=job_id,
    )
    session.add(entry)
    await session.commit()
    return entry


async def query_reviewables(session: AsyncSession) -> list[(Job, LedgerEntry | None)]:
    statement = (
        select(Job, LedgerEntry)
        .join(LedgerEntry, onclause=LedgerEntry.job_id == Job.id, isouter=True)
        .where(or_(Job.status == "needs_review", LedgerEntry.needs_review == True))
    )
    results = await session.exec(statement)
    reviewables = []
    for row in results:
        reviewables.append((row[0], row[1]))
    return reviewables


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
