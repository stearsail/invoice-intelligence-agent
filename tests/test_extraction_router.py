from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_agent.api.routers import extraction
from invoice_agent.db.operations import create_job, query_job
from invoice_agent.reconciliation import ReconciliationIssue


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def in_memory_session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(extraction, "session_factory", factory)
    yield factory
    await engine.dispose()


async def _make_job(in_memory_session_factory, file_key: str = "a1b2c3d4.png"):
    async with in_memory_session_factory() as session:
        return await create_job(session, file_key=file_key)


@pytest.mark.anyio
async def test_run_agent_marks_job_complete_on_success(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value={"invoice": MagicMock()})
    monkeypatch.setattr(extraction.graph, "ainvoke", fake_graph.ainvoke)

    await extraction._run_agent(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "complete"
    assert updated.error is None


@pytest.mark.anyio
async def test_run_agent_marks_job_extraction_failed_when_no_invoice_extracted(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(
        return_value={
            "invoice": None,
            "reconciliation_issues": [
                ReconciliationIssue(
                    category="unverifiable",
                    message="Extraction failed entirely — no invoice to reconcile",
                )
            ],
        }
    )
    monkeypatch.setattr(extraction.graph, "ainvoke", fake_graph.ainvoke)

    await extraction._run_agent(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "extraction_failed"
    assert "Extraction failed entirely" in updated.error


@pytest.mark.anyio
async def test_run_agent_marks_job_error_when_graph_raises(
    in_memory_session_factory, monkeypatch
):
    job = await _make_job(in_memory_session_factory)
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=RuntimeError("vllm connection refused"))
    monkeypatch.setattr(extraction.graph, "ainvoke", fake_graph.ainvoke)

    await extraction._run_agent(job.id, job.file_key)

    async with in_memory_session_factory() as session:
        updated = await query_job(session, job.id)
    assert updated.status == "error"
    assert "vllm connection refused" in updated.error
