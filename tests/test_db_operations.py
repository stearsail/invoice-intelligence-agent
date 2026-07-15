from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_agent.db.operations import create_job, find_duplicate, write_entry
from invoice_agent.schema import Invoice, Party


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as s:
        yield s
    await engine.dispose()


def _invoice(**overrides) -> Invoice:
    defaults = {
        "document_type": "receipt",
        "currency": "USD",
        "grand_total": Decimal("10.00"),
    }
    defaults.update(overrides)
    return Invoice(**defaults)


@pytest.mark.anyio
async def test_write_invoice_persists_and_assigns_id(session):
    entry = await write_entry(session, _invoice())

    assert entry.id is not None
    assert entry.grand_total == Decimal("10.00")
    assert entry.currency == "USD"


@pytest.mark.anyio
async def test_write_invoice_stores_vendor_name_when_present(session):
    invoice = _invoice(vendor=Party(name="Acme Supplies SRL"))

    entry = await write_entry(session, invoice)

    assert entry.vendor_name == "Acme Supplies SRL"


@pytest.mark.anyio
async def test_write_invoice_vendor_name_is_none_when_vendor_missing(session):
    entry = await write_entry(session, _invoice())

    assert entry.vendor_name is None


@pytest.mark.anyio
async def test_write_invoice_stores_full_invoice_as_json(session):
    invoice = _invoice(invoice_number="INV-001", issue_date=date(2026, 7, 1))

    entry = await write_entry(session, invoice)
    restored = Invoice.model_validate(entry.invoice_data)

    assert restored.invoice_number == "INV-001"
    assert restored.issue_date == date(2026, 7, 1)
    assert restored.grand_total == Decimal("10.00")


@pytest.mark.anyio
async def test_multiple_writes_get_distinct_ids(session):
    entry_one = await write_entry(session, _invoice(invoice_number="A"))
    entry_two = await write_entry(session, _invoice(invoice_number="B"))

    assert entry_one.id != entry_two.id


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_nothing_matches(session):
    assert await find_duplicate(session, "INV-001", "Acme Supplies SRL") is None


@pytest.mark.anyio
async def test_find_duplicate_finds_same_invoice_number_and_vendor(session):
    invoice = _invoice(invoice_number="INV-001", vendor=Party(name="Acme Supplies SRL"))
    written = await write_entry(session, invoice)

    duplicate = await find_duplicate(session, "INV-001", "Acme Supplies SRL")

    assert duplicate is not None
    assert duplicate.id == written.id


@pytest.mark.anyio
async def test_find_duplicate_ignores_same_number_different_vendor(session):
    await write_entry(
        session,
        _invoice(invoice_number="INV-001", vendor=Party(name="Acme Supplies SRL")),
    )

    duplicate = await find_duplicate(session, "INV-001", "Beta Corp GmbH")

    assert duplicate is None


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_invoice_number_missing():
    assert await find_duplicate(object(), None, "Acme Supplies SRL") is None


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_vendor_name_missing():
    assert await find_duplicate(object(), "INV-001", None) is None


@pytest.mark.anyio
async def test_create_job_persists_and_assigns_id(session):
    job = await create_job(session, file_key="a1b2c3d4.png")

    assert job.id is not None
    assert job.status == "pending"
    assert job.file_key == "a1b2c3d4.png"
    assert job.ledger_entry_id is None


@pytest.mark.anyio
async def test_create_job_stores_ledger_entry_id_when_given(session):
    entry = await write_entry(session, _invoice())

    job = await create_job(session, file_key="a1b2c3d4.png", ledger_entry_id=entry.id)

    assert job.ledger_entry_id == entry.id


@pytest.mark.anyio
async def test_multiple_jobs_get_distinct_ids(session):
    job_one = await create_job(session, file_key="a1b2c3d4.png")
    job_two = await create_job(session, file_key="e5f6g7h8.png")

    assert job_one.id != job_two.id
