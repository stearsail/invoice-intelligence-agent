from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_agent.agent.runner import ExtractionResult
from invoice_agent.db.operations import create_job, query_job
from invoice_agent.services import extraction_job


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def in_memory_session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(extraction_job, "session_factory", factory)
    yield factory
    await engine.dispose()


async def _make_job(in_memory_session_factory, file_key: str = "a1b2c3d4.png"):
    async with in_memory_session_factory() as session:
        return await create_job(session, file_key=file_key)


@pytest.mark.anyio
async def test_marks_job_complete_on_success(in_memory_session_factory, monkeypatch):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        extraction_job,
        "run_extraction",
        AsyncMock(return_value=ExtractionResult(status="complete", ledger_entry_id=1)),
    )

    await extraction_job.run_extraction_job(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "complete"
    assert updated.error is None


@pytest.mark.anyio
async def test_marks_job_extraction_failed_when_no_invoice_extracted(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        extraction_job,
        "run_extraction",
        AsyncMock(
            return_value=ExtractionResult(
                status="extraction_failed",
                error="Extraction failed entirely — no invoice to reconcile",
            )
        ),
    )

    await extraction_job.run_extraction_job(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "extraction_failed"
    assert "Extraction failed entirely" in updated.error


@pytest.mark.anyio
async def test_marks_job_error_when_extraction_raises(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        extraction_job,
        "run_extraction",
        AsyncMock(side_effect=RuntimeError("vllm connection refused")),
    )

    await extraction_job.run_extraction_job(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "error"
    assert "vllm connection refused" in updated.error


@pytest.mark.anyio
async def test_resolves_file_key_against_uploads_dir(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory, file_key="a1b2c3d4.png")
    fake_run = AsyncMock(return_value=ExtractionResult(status="complete"))
    monkeypatch.setattr(extraction_job, "run_extraction", fake_run)

    await extraction_job.run_extraction_job(job.id, job.file_key)

    img_path = fake_run.await_args.kwargs["img_path"]
    assert img_path.endswith("a1b2c3d4.png")
    assert str(extraction_job.UPLOADS_DIR) in img_path
