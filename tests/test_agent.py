from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from invoice_agent import agent
from invoice_agent.schema import Invoice, LineItem


def _invoice(**overrides) -> Invoice:
    defaults = dict(
        document_type="receipt",
        currency="USD",
        invoice_number="INV-1",
        grand_total=Decimal("100"),
        subtotal=Decimal("100"),
        line_items=[
            LineItem(
                description="Item",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            ),
        ],
    )
    defaults.update(overrides)
    return Invoice(**defaults)


def _fake_specialist_client(content: str) -> MagicMock:
    message = MagicMock(content=content)
    choice = MagicMock(message=message)
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[choice])
    )
    return fake_client


def _fake_frontier_model(
    invoice: Invoice | None = None, raises: bool = False
) -> MagicMock:
    structured = MagicMock()
    if raises:
        structured.ainvoke = AsyncMock(side_effect=RuntimeError("frontier boom"))
    else:
        structured.ainvoke = AsyncMock(return_value=invoice)
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value = structured
    return fake_model


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_image_io(monkeypatch):
    monkeypatch.setattr(agent, "load_image_b64", lambda path: "fakeb64")


@pytest.fixture(autouse=True)
def no_real_ledger(monkeypatch):
    async def _find_duplicate(session_factory, invoice_number, vendor_name):
        return None

    monkeypatch.setattr(agent, "find_duplicate", _find_duplicate)

    written = []

    async def _write(session_factory, invoice, needs_review=False, review_reason=None):
        written.append(
            {
                "invoice": invoice,
                "needs_review": needs_review,
                "review_reason": review_reason,
            }
        )
        return MagicMock(id=1)

    monkeypatch.setattr(agent, "write_invoice", _write)
    return written


@pytest.mark.anyio
async def test_specialist_success_reconciles_and_writes_ledger(
    monkeypatch, no_real_ledger
):
    invoice = _invoice()
    monkeypatch.setattr(
        agent, "client", _fake_specialist_client(invoice.model_dump_json())
    )

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["attempt"] == "specialist"
    assert result["reconciliation_issues"] == []
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is False


@pytest.mark.anyio
async def test_specialist_parse_failure_falls_back_to_frontier_and_succeeds(
    monkeypatch, no_real_ledger
):
    invoice = _invoice()
    monkeypatch.setattr(agent, "client", _fake_specialist_client("not valid json"))
    monkeypatch.setattr(agent, "model", _fake_frontier_model(invoice))

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["attempt"] == "frontier"
    assert result["reconciliation_issues"] == []
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is False


@pytest.mark.anyio
async def test_both_specialist_and_frontier_extraction_fail_goes_to_human_review(
    monkeypatch, no_real_ledger
):
    monkeypatch.setattr(agent, "client", _fake_specialist_client("not valid json"))
    monkeypatch.setattr(agent, "model", _fake_frontier_model(raises=True))

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["invoice"] is None
    assert result["reconciliation_issues"] == [
        "extraction failed entirely — no invoice to reconcile"
    ]
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    assert "extraction failed entirely" in no_real_ledger[0]["review_reason"]


@pytest.mark.anyio
async def test_specialist_reconciliation_failure_retries_via_frontier_and_resolves(
    monkeypatch, no_real_ledger
):
    bad_invoice = _invoice(grand_total=Decimal("500"))
    good_invoice = _invoice()
    monkeypatch.setattr(
        agent, "client", _fake_specialist_client(bad_invoice.model_dump_json())
    )
    monkeypatch.setattr(agent, "model", _fake_frontier_model(good_invoice))

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["attempt"] == "frontier"
    assert result["reconciliation_issues"] == []
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is False


@pytest.mark.anyio
async def test_reconciliation_failure_persists_after_frontier_retry_goes_to_human_review(
    monkeypatch, no_real_ledger
):
    bad_invoice = _invoice(grand_total=Decimal("500"))
    monkeypatch.setattr(
        agent, "client", _fake_specialist_client(bad_invoice.model_dump_json())
    )
    monkeypatch.setattr(agent, "model", _fake_frontier_model(bad_invoice))

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["attempt"] == "frontier"
    assert len(result["reconciliation_issues"]) == 1
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    assert "grand total computation" in no_real_ledger[0]["review_reason"]


@pytest.mark.anyio
async def test_duplicate_after_frontier_fallback_goes_to_human_review(
    monkeypatch, no_real_ledger
):
    invoice = _invoice()
    monkeypatch.setattr(agent, "client", _fake_specialist_client("not valid json"))
    monkeypatch.setattr(agent, "model", _fake_frontier_model(invoice))

    async def _dup(session_factory, invoice_number, vendor_name):
        return MagicMock(id=42)

    monkeypatch.setattr(agent, "find_duplicate", _dup)

    result = await agent.graph.ainvoke({"image": "fake.png", "invoice": None})

    assert result["attempt"] == "frontier"
    assert any("duplicate" in issue for issue in result["reconciliation_issues"])
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    assert "duplicate" in no_real_ledger[0]["review_reason"]
