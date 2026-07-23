import asyncio
import logging
from invoice_agent.agent.runner import run_extraction
from invoice_agent.db.engine import session_factory
from invoice_agent.db.operations import update_job
from invoice_agent.config import UPLOADS_DIR, MAX_CONCURRENCY

logger = logging.getLogger(__name__)
_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


async def _set_status(job_id: int, status: str, error: str | None = None):
    async with session_factory() as session:
        await update_job(
            session, job_id=job_id, status_update=status, error_update=error
        )


async def _run_extraction_job(job_id: int, file_key: str) -> None:
    img_path = str(UPLOADS_DIR / file_key)
    try:
        result = await run_extraction(job_id=job_id, img_path=img_path)
    except Exception as e:
        logger.exception("Extraction job %s failed", job_id)
        await _set_status(job_id, status="error", error=str(e))
        return
    await _set_status(job_id, status=result.status, error=result.error)


async def run_extraction_batch(jobs: list[tuple[int, str]]):

    async def _run_one(job_id, file_key):
        async with _semaphore:
            await _run_extraction_job(job_id, file_key)

    await asyncio.gather(*(_run_one(j, f) for j, f in jobs))
