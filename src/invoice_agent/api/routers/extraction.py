import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession
from invoice_agent.api.schema.responses import FileUploadResponse
from invoice_agent.db.engine import get_async_session
from invoice_agent.db.operations import create_job


router = APIRouter(prefix="/extraction", tags=["extraction"])


_ALLOWED_TYPES = {"image/jpeg": "jpeg", "image/png": "png", "application/pdf": "pdf"}
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


@router.post("/upload_image")
async def upload(file: UploadFile, session: AsyncSession = Depends(get_async_session)):
    _check_file_type(file)
    key = _build_file_key(file)
    await _save_upload(file, key)
    job = await create_job(session, key)
    return FileUploadResponse(job_id=job.id, status=job.status)
