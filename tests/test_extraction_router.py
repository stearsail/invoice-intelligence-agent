import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_agent.api.routers import extraction


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def in_memory_session_factory(monkeypatch, tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(extraction, "UPLOADS_DIR", tmp_path)
    yield factory
    await engine.dispose()


def _upload_file(name: str, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"fake-image-bytes"),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.anyio
async def test_upload_creates_one_job_per_file(in_memory_session_factory):
    files = [_upload_file("a.png"), _upload_file("b.png"), _upload_file("c.png")]

    async with in_memory_session_factory() as session:
        responses = await extraction.upload(
            files=files, session=session, pool=AsyncMock()
        )

    assert len(responses) == 3
    assert [r.status for r in responses] == ["pending", "pending", "pending"]
    assert len({r.job_id for r in responses}) == 3


@pytest.mark.anyio
async def test_upload_enqueues_a_job_for_every_created_job(in_memory_session_factory):
    pool = AsyncMock()
    files = [_upload_file("a.png"), _upload_file("b.png")]

    async with in_memory_session_factory() as session:
        responses = await extraction.upload(files=files, session=session, pool=pool)

    enqueued_job_ids = {call.args[1] for call in pool.enqueue_job.await_args_list}
    assert enqueued_job_ids == {r.job_id for r in responses}
    assert all(
        call.args[0] == "process_job" for call in pool.enqueue_job.await_args_list
    )


@pytest.mark.anyio
async def test_upload_rejects_invalid_file_type(in_memory_session_factory):
    files = [_upload_file("a.png"), _upload_file("doc.txt", content_type="text/plain")]

    with pytest.raises(HTTPException):
        async with in_memory_session_factory() as session:
            await extraction.upload(files=files, session=session, pool=AsyncMock())
