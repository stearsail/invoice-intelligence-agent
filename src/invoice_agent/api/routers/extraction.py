import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from invoice_agent.api.schema.responses import JobCreationResponse
from invoice_agent.db.engine import get_async_session, session_factory
from invoice_agent.db.operations import create_job, update_job, query_job
from invoice_agent.agent import graph


router = APIRouter(prefix="/extraction", tags=["extraction"])


_ALLOWED_TYPES = {"image/jpeg": "jpeg", "image/png": "png"}
# LOCAL STORAGE FOR PROJECT SCOPE, NO S3/R2
UPLOADS_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _check_file_type(file: UploadFile) -> None:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"File type cannot be accessed: '{file.content_type}'. Please upload PNG, JPEG or PDF.",
        )


def _build_file_key(file: UploadFile) -> str:
    ext = _ALLOWED_TYPES[file.content_type]
    key = f"{uuid.uuid4()}.{ext}"
    return key


async def _save_upload(file: UploadFile, key: str) -> None:
    async with aiofiles.open(UPLOADS_DIR / key, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)


async def _run_agent(job_id: int, job_file_key: str) -> None:
    try:
        result = await graph.ainvoke(
            input={
                "job_id": job_id,
                "image": str(UPLOADS_DIR / job_file_key),
                "invoice": None,
            }
        )
    except Exception as e:
        async with session_factory() as session:
            await update_job(
                session, job_id=job_id, status_update="error", error_update=str(e)
            )
        return
    async with session_factory() as session:
        if result["invoice"] is None:
            await update_job(
                session,
                job_id=job_id,
                status_update="extraction_failed",
                error_update="; ".join(
                    issue.message for issue in result["reconciliation_issues"]
                ),
            )
        else:
            await update_job(session, job_id=job_id, status_update="complete")


@router.post("/upload_image")
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> JobCreationResponse:
    _check_file_type(file)
    key = _build_file_key(file)
    await _save_upload(file, key)
    job = await create_job(session, key)
    background_tasks.add_task(_run_agent, job.id, job.file_key)
    return JobCreationResponse(job_id=job.id, status=job.status)


@router.get("/status/{job_id}")
async def get_extraction_job(
    job_id: int, session: AsyncSession = Depends(get_async_session)
):
    job = await query_job(session, job_id)
    return {"job": job}


@router.get("/image/{job_id}")
async def get_job_image(
    job_id: int, session: AsyncSession = Depends(get_async_session)
) -> FileResponse:
    job = await query_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    key = job.file_key
    file_path = UPLOADS_DIR / key
    if not Path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image does not exist")
    return FileResponse(file_path)
