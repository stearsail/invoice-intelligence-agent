from arq import Retry
from arq.connections import RedisSettings
from invoice_agent import config
import logging
from invoice_agent.agent.runner import run_extraction
from invoice_agent.db.engine import session_factory
from invoice_agent.db.operations import update_job
from invoice_agent.config import UPLOADS_DIR

logger = logging.getLogger(__name__)


async def _set_status(
    job_id: int, status: str, attempts: int, error: str | None = None
):
    async with session_factory() as session:
        await update_job(
            session,
            job_id=job_id,
            status_update=status,
            attempts_update=attempts,
            error_update=error,
        )


async def _run_extraction_job(job_id: int, file_key: str) -> None:
    img_path = str(UPLOADS_DIR / file_key)
    return await run_extraction(job_id=job_id, img_path=img_path)


async def process_job(ctx, job_id, file_key):
    try:
        result = await _run_extraction_job(job_id, file_key)
    except Exception as e:
        if ctx["job_try"] < WorkerSettings.max_tries:
            async with session_factory() as session:
                await update_job(
                    session,
                    job_id=job_id,
                    status_update="retrying",
                    error_update=str(e),
                    attempts_update=ctx["job_try"],
                )
            raise Retry(defer=ctx["job_try"] * 10)
        else:
            logger.exception("Extraction job %s failed permanently", job_id)
            await _set_status(
                job_id, status="error", attempts=ctx["job_try"], error=str(e)
            )
            return
    await _set_status(
        job_id, status=result.status, attempts=ctx["job_try"], error=result.error
    )


class WorkerSettings:
    redis_settings = RedisSettings(host=config.REDIS_HOST, port=config.REDIS_PORT)
    functions = [process_job]
    max_tries = 3
