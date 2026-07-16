from datetime import datetime
from decimal import Decimal

from invoice_agent.api.routers.ledger import _to_response
from invoice_agent.db.models import Job, LedgerEntry


def _job(**overrides) -> Job:
    defaults = dict(
        id=1,
        status="complete",
        error=None,
        file_key="a1b2c3d4.png",
        created_at=datetime(2026, 7, 15, 12, 0, 0),
    )
    defaults.update(overrides)
    return Job(**defaults)


def _entry(**overrides) -> LedgerEntry:
    defaults = dict(
        id=1,
        invoice_number=None,
        vendor_name=None,
        issue_date=None,
        currency="USD",
        grand_total=Decimal("10.00"),
        invoice_data={
            "document_type": "receipt",
            "currency": "USD",
            "grand_total": "10.00",
        },
        created_at=datetime(2026, 7, 15, 12, 0, 0),
        needs_review=False,
        review_reason=None,
        job_id=1,
    )
    defaults.update(overrides)
    return LedgerEntry(**defaults)


def test_to_response_with_no_entry():
    job = _job(status="needs_review", error="extraction failed entirely")

    response = _to_response(job, None)

    assert response.job_id == 1
    assert response.status == "needs_review"
    assert response.error == "extraction failed entirely"
    assert response.ledger_entry is None
    assert response.ledger_entry_error is None


def test_to_response_with_valid_entry():
    job = _job()
    entry = _entry(needs_review=True, review_reason="unverifiable: missing subtotal")

    response = _to_response(job, entry)

    assert response.ledger_entry is not None
    assert response.ledger_entry.needs_review is True
    assert response.ledger_entry.review_reason == "unverifiable: missing subtotal"
    assert response.ledger_entry.invoice_data.document_type == "receipt"
    assert response.ledger_entry_error is None


def test_to_response_degrades_gracefully_on_corrupt_invoice_data():
    job = _job()
    entry = _entry(invoice_data={"this": "does not match the Invoice schema at all"})

    response = _to_response(job, entry)

    # the whole row must still come back, not raise — job-level fields stay populated
    assert response.job_id == 1
    assert response.status == "complete"
    assert response.ledger_entry is None
    assert response.ledger_entry_error is not None
    assert "document_type" in response.ledger_entry_error
