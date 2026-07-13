from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, create_engine

from invoice_agent.db.operations import write_invoice
from invoice_agent.schema import Invoice, Party


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _invoice(**overrides) -> Invoice:
    defaults = {
        "document_type": "receipt",
        "currency": "USD",
        "grand_total": Decimal("10.00"),
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def test_write_invoice_persists_and_assigns_id(test_engine):
    entry = write_invoice(test_engine, _invoice())

    assert entry.id is not None
    assert entry.grand_total == Decimal("10.00")
    assert entry.currency == "USD"


def test_write_invoice_stores_vendor_name_when_present(test_engine):
    invoice = _invoice(vendor=Party(name="Acme Supplies SRL"))

    entry = write_invoice(test_engine, invoice)

    assert entry.vendor_name == "Acme Supplies SRL"


def test_write_invoice_vendor_name_is_none_when_vendor_missing(test_engine):
    entry = write_invoice(test_engine, _invoice())

    assert entry.vendor_name is None


def test_write_invoice_stores_full_invoice_as_json(test_engine):
    invoice = _invoice(invoice_number="INV-001", issue_date=date(2026, 7, 1))

    entry = write_invoice(test_engine, invoice)
    restored = Invoice.model_validate(entry.invoice_data)

    assert restored.invoice_number == "INV-001"
    assert restored.issue_date == date(2026, 7, 1)
    assert restored.grand_total == Decimal("10.00")


def test_multiple_writes_get_distinct_ids(test_engine):
    entry_one = write_invoice(test_engine, _invoice(invoice_number="A"))
    entry_two = write_invoice(test_engine, _invoice(invoice_number="B"))

    assert entry_one.id != entry_two.id
