from unittest.mock import AsyncMock

import pytest
from arq import Retry
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_pipeline.workflow.runner import ExtractionResult
from invoice_pipeline.db.operations import create_job, query_job
from invoice_pipeline.queue import worker


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def in_memory_session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(worker, "session_factory", factory)
    yield factory
    await engine.dispose()


async def _make_job(in_memory_session_factory, file_key: str = "a1b2c3d4.png"):
    async with in_memory_session_factory() as session:
        return await create_job(session, file_key=file_key)


@pytest.mark.anyio
async def test_run_extraction_job_resolves_file_key_against_uploads_dir(monkeypatch):
    fake_run = AsyncMock(return_value=ExtractionResult(status="complete"))
    monkeypatch.setattr(worker, "run_extraction", fake_run)

    await worker._run_extraction_job(1, "a1b2c3d4.png")

    img_path = fake_run.await_args.kwargs["img_path"]
    assert img_path.endswith("a1b2c3d4.png")
    assert str(worker.UPLOADS_DIR) in img_path


@pytest.mark.anyio
async def test_process_job_marks_complete_on_success(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        worker,
        "run_extraction",
        AsyncMock(return_value=ExtractionResult(status="complete", ledger_entry_id=1)),
    )

    await worker.process_job({"job_try": 1}, job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "complete"
    assert updated.error is None
    assert updated.attempts == 1


@pytest.mark.anyio
async def test_process_job_marks_extraction_failed_when_no_invoice_extracted(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        worker,
        "run_extraction",
        AsyncMock(
            return_value=ExtractionResult(
                status="extraction_failed",
                error="Extraction failed entirely — unknown: no invoice to reconcile",
            )
        ),
    )

    await worker.process_job({"job_try": 1}, job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "extraction_failed"
    assert "Extraction failed entirely" in updated.error


@pytest.mark.anyio
async def test_process_job_retries_when_tries_remain(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        worker,
        "run_extraction",
        AsyncMock(side_effect=RuntimeError("vllm connection refused")),
    )

    with pytest.raises(Retry):
        await worker.process_job({"job_try": 1}, job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "retrying"
    assert updated.attempts == 1
    assert "vllm connection refused" in updated.error


@pytest.mark.anyio
async def test_process_job_marks_error_when_tries_exhausted(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    monkeypatch.setattr(
        worker,
        "run_extraction",
        AsyncMock(side_effect=RuntimeError("vllm connection refused")),
    )
    last_try = worker.WorkerSettings.max_tries

    await worker.process_job({"job_try": last_try}, job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "error"
    assert updated.attempts == last_try
    assert "vllm connection refused" in updated.error
