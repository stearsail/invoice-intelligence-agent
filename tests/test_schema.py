from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invoice_pipeline.schema import Invoice

FULL_INVOICE = {
    "document_type": "invoice",
    "vendor": {
        "name": "SC Exemplu SRL",
        "address": "Str. Victoriei 12, Bucuresti",
        "tax_id": "RO12345678",
        "iban": "RO49AAAA1B31007593840000",
    },
    "customer": {
        "name": "Acme GmbH",
        "address": "Hauptstrasse 5, Berlin",
        "tax_id": "DE999999999",
    },
    "invoice_number": "INV-2026-0042",
    "issue_date": "2026-07-01",
    "due_date": "2026-07-31",
    "currency": "RON",
    "line_items": [
        {
            "description": "Consulting services",
            "quantity": "10",
            "unit_price": "150.00",
            "line_total": "1500.00",
        },
        {
            "description": None,
            "quantity": "1.5",
            "unit_price": "99.90",
            "line_total": "149.85",
        },
    ],
    "grand_total": "1649.85",
    "confidence_notes": ["due_date was printed faintly"],
}

MINIMAL_RECEIPT = {
    "document_type": "receipt",
    "currency": "EUR",
    "grand_total": "12.50",
}


def test_full_invoice_parses():
    invoice = Invoice.model_validate(FULL_INVOICE)

    assert invoice.document_type == "invoice"
    assert invoice.vendor is not None
    assert invoice.vendor.name == "SC Exemplu SRL"
    assert invoice.issue_date == date(2026, 7, 1)
    assert invoice.grand_total == Decimal("1649.85")
    assert len(invoice.line_items) == 2
    assert invoice.line_items[0].unit_price == Decimal("150.00")
    assert invoice.line_items[1].description is None


def test_minimal_receipt_parses_with_defaults():
    receipt = Invoice.model_validate(MINIMAL_RECEIPT)

    assert receipt.vendor is None
    assert receipt.customer is None
    assert receipt.invoice_number is None
    assert receipt.issue_date is None
    assert receipt.line_items == []
    assert receipt.confidence_notes == []


@pytest.mark.parametrize(
    "corruption",
    [
        pytest.param({"grand_total": None}, id="missing-grand-total"),
        pytest.param({"issue_date": "01/07/2026"}, id="non-iso-date"),
        pytest.param({"currency": "eur"}, id="lowercase-currency"),
        pytest.param({"currency": "EURO"}, id="four-letter-currency"),
        pytest.param({"document_type": "quote"}, id="unknown-document-type"),
        pytest.param({"total_amount": "10.00"}, id="hallucinated-extra-key"),
    ],
)
def test_rejects_malformed_input(corruption):
    data = {**MINIMAL_RECEIPT, **corruption}
    data = {key: value for key, value in data.items() if value is not None}

    with pytest.raises(ValidationError):
        Invoice.model_validate(data)


def test_json_round_trip_preserves_values_exactly():
    original = Invoice.model_validate(FULL_INVOICE)

    restored = Invoice.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.grand_total == Decimal("1649.85")
    assert restored.line_items[1].line_total == Decimal("149.85")
    assert restored.issue_date == date(2026, 7, 1)
