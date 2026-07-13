from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from invoice_agent.db.operations import find_duplicate, write_invoice
from invoice_agent.schema import Invoice, Party


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
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
async def test_write_invoice_persists_and_assigns_id(session_factory):
    entry = await write_invoice(session_factory, _invoice())

    assert entry.id is not None
    assert entry.grand_total == Decimal("10.00")
    assert entry.currency == "USD"


@pytest.mark.anyio
async def test_write_invoice_stores_vendor_name_when_present(session_factory):
    invoice = _invoice(vendor=Party(name="Acme Supplies SRL"))

    entry = await write_invoice(session_factory, invoice)

    assert entry.vendor_name == "Acme Supplies SRL"


@pytest.mark.anyio
async def test_write_invoice_vendor_name_is_none_when_vendor_missing(session_factory):
    entry = await write_invoice(session_factory, _invoice())

    assert entry.vendor_name is None


@pytest.mark.anyio
async def test_write_invoice_stores_full_invoice_as_json(session_factory):
    invoice = _invoice(invoice_number="INV-001", issue_date=date(2026, 7, 1))

    entry = await write_invoice(session_factory, invoice)
    restored = Invoice.model_validate(entry.invoice_data)

    assert restored.invoice_number == "INV-001"
    assert restored.issue_date == date(2026, 7, 1)
    assert restored.grand_total == Decimal("10.00")


@pytest.mark.anyio
async def test_multiple_writes_get_distinct_ids(session_factory):
    entry_one = await write_invoice(session_factory, _invoice(invoice_number="A"))
    entry_two = await write_invoice(session_factory, _invoice(invoice_number="B"))

    assert entry_one.id != entry_two.id


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_nothing_matches(session_factory):
    assert await find_duplicate(session_factory, "INV-001", "Acme Supplies SRL") is None


@pytest.mark.anyio
async def test_find_duplicate_finds_same_invoice_number_and_vendor(session_factory):
    invoice = _invoice(invoice_number="INV-001", vendor=Party(name="Acme Supplies SRL"))
    written = await write_invoice(session_factory, invoice)

    duplicate = await find_duplicate(session_factory, "INV-001", "Acme Supplies SRL")

    assert duplicate is not None
    assert duplicate.id == written.id


@pytest.mark.anyio
async def test_find_duplicate_ignores_same_number_different_vendor(session_factory):
    await write_invoice(
        session_factory,
        _invoice(invoice_number="INV-001", vendor=Party(name="Acme Supplies SRL")),
    )

    duplicate = await find_duplicate(session_factory, "INV-001", "Beta Corp GmbH")

    assert duplicate is None


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_invoice_number_missing():
    assert await find_duplicate(object(), None, "Acme Supplies SRL") is None


@pytest.mark.anyio
async def test_find_duplicate_returns_none_when_vendor_name_missing():
    assert await find_duplicate(object(), "INV-001", None) is None
