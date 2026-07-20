from fastapi import APIRouter, HTTPException, Depends
import logging
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from invoice_agent.api.schema.responses import (
    LedgerEntryResponse,
    JobEntryPairResponse,
    PendingJobResponse,
)
from invoice_agent.db.engine import get_async_session
from invoice_agent.db.models import Job, LedgerEntry
from invoice_agent.db.operations import (
    query_job_entry,
    query_pending_jobs,
    query_resolved_ledger,
    query_reviewables,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ledger", tags=["ledger"])


def _to_response(job: Job, entry: LedgerEntry | None) -> JobEntryPairResponse:
    ledger_entry = None
    ledger_entry_error = None
    if entry is not None:
        try:
            ledger_entry = LedgerEntryResponse.model_validate(entry)
        except ValidationError as e:
            logger.error(
                "Failed to decode ledger entry %s for job %s: %s",
                entry.id,
                job.id,
                e,
            )
            ledger_entry_error = str(e)
    return JobEntryPairResponse(
        job_id=job.id,
        created_at=job.created_at,
        status=job.status,
        error=job.error,
        ledger_entry=ledger_entry,
        ledger_entry_error=ledger_entry_error,
    )


def _to_pending_response(job: Job) -> PendingJobResponse:
    return PendingJobResponse(job_id=job.id, created_at=job.created_at)


@router.get("/review", response_model=list[JobEntryPairResponse])
async def get_reviewables(
    session: AsyncSession = Depends(get_async_session),
) -> list[JobEntryPairResponse]:
    results = await query_reviewables(session)
    reviewables = []
    for job, entry in results:
        reviewables.append((_to_response(job, entry)))
    return reviewables


@router.get("/resolved", response_model=list[JobEntryPairResponse])
async def get_full_ledger(session: AsyncSession = Depends(get_async_session)):
    results = await query_resolved_ledger(session)
    entries = []
    for job, entry in results:
        entries.append((_to_response(job, entry)))
    return entries


@router.get("/pending", response_model=list[PendingJobResponse])
async def get_pending_jobs(
    session: AsyncSession = Depends(get_async_session),
) -> list[PendingJobResponse]:
    results = await query_pending_jobs(session)
    pending = []
    for job in results:
        pending.append(_to_pending_response(job))
    return pending


@router.get("/{job_id}", response_model=JobEntryPairResponse)
async def get_job_by_id(
    job_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> JobEntryPairResponse:
    result = await query_job_entry(session, job_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )
    job, entry = result
    return _to_response(job, entry)
