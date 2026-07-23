from invoice_agent.services.extraction_job import run_extraction_batch
import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from invoice_agent.api.schema.responses import JobCreationResponse
from invoice_agent.db.engine import get_async_session
from invoice_agent.db.operations import create_job, query_job
from invoice_agent.config import UPLOADS_DIR


router = APIRouter(prefix="/extraction", tags=["extraction"])

_ALLOWED_TYPES = {"image/jpeg": "jpeg", "image/png": "png"}


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


@router.post("/upload_image")
async def upload(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> list[JobCreationResponse]:
    created_jobs = []
    for file in files:
        _check_file_type(file)
        key = _build_file_key(file)
        await _save_upload(file, key)
        job = await create_job(session, key)
        created_jobs.append(job)
    background_tasks.add_task(
        run_extraction_batch, [(job.id, job.file_key) for job in created_jobs]
    )
    return [
        JobCreationResponse(job_id=job.id, status=job.status) for job in created_jobs
    ]


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
