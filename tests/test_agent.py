from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from invoice_agent.agent import nodes
from invoice_agent.agent.extractors import ExtractionResult
from invoice_agent.agent.graph import build_graph
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


class _FakeExtractor:
    """Stands in for a real extractor at the graph boundary.

    Returns a canned ExtractionResult and records how it was called, so tests
    can assert on the context fed back during the review retry.
    """

    def __init__(self, result: ExtractionResult | None = None):
        self.result = result
        self.calls = []

    async def extract_invoice(
        self, img_path: str, extra_context: str | None = None
    ) -> ExtractionResult:
        self.calls.append({"img_path": img_path, "extra_context": extra_context})
        return self.result


def _extracted(invoice: Invoice) -> ExtractionResult:
    return ExtractionResult(invoice=invoice, parse_error=None)


def _failed(parse_error: str) -> ExtractionResult:
    return ExtractionResult(invoice=None, parse_error=parse_error)


def _build(specialist_result=None, frontier_result=None):
    """Compile a graph wired to fake extractors."""
    specialist = _FakeExtractor(specialist_result)
    frontier = _FakeExtractor(frontier_result)
    return build_graph(specialist=specialist, frontier=frontier), specialist, frontier


def _initial_state(**overrides):
    state = {"job_id": 1, "image": "fake.png", "invoice": None}
    state.update(overrides)
    return state


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_ledger(monkeypatch):
    async def _find_duplicate(session, invoice_number, vendor_name):
        return None

    monkeypatch.setattr(nodes, "find_duplicate", _find_duplicate)

    written = []

    async def _write(session, job_id, invoice, needs_review=False, review_reason=None):
        written.append(
            {
                "job_id": job_id,
                "invoice": invoice,
                "needs_review": needs_review,
                "review_reason": review_reason,
            }
        )
        return MagicMock(id=1)

    monkeypatch.setattr(nodes, "write_entry", _write)
    return written


@pytest.mark.anyio
async def test_specialist_success_reconciles_and_writes_ledger(no_real_ledger):
    graph, _, _ = _build(specialist_result=_extracted(_invoice()))

    result = await graph.ainvoke(_initial_state())

    assert result["attempt"] == "specialist"
    assert result["reconciliation_issues"] == []
    assert len(no_real_ledger) == 1
    # Every entry gets a human confirmation pass, even a clean reconciliation —
    # needs_review only flips to False once a verifier actually saves it.
    assert no_real_ledger[0]["needs_review"] is True
    assert no_real_ledger[0]["review_reason"] == []
    assert no_real_ledger[0]["job_id"] == 1


@pytest.mark.anyio
async def test_specialist_parse_failure_falls_back_to_frontier_and_succeeds(
    no_real_ledger,
):
    graph, _, frontier = _build(
        specialist_result=_failed("Pydantic Validation error: not valid json"),
        frontier_result=_extracted(_invoice()),
    )

    result = await graph.ainvoke(_initial_state())

    assert result["attempt"] == "frontier"
    assert result["reconciliation_issues"] == []
    assert len(frontier.calls) == 1
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True


@pytest.mark.anyio
async def test_both_specialist_and_frontier_extraction_fail_skips_ledger_write(
    no_real_ledger,
):
    graph, _, _ = _build(
        specialist_result=_failed("Pydantic Validation error: not valid json"),
        frontier_result=_failed("Frontier structured output error: frontier boom"),
    )

    result = await graph.ainvoke(_initial_state())

    assert result["invoice"] is None
    assert len(result["reconciliation_issues"]) == 1
    assert result["reconciliation_issues"][0].category == "unverifiable"
    assert (
        result["reconciliation_issues"][0].message
        == "Extraction failed entirely — Frontier structured output error: frontier boom"
    )
    # total failure routes straight to END — nothing to write, no ledger entry created
    assert no_real_ledger == []


@pytest.mark.anyio
async def test_specialist_reconciliation_failure_retries_via_frontier_and_resolves(
    no_real_ledger,
):
    graph, _, _ = _build(
        specialist_result=_extracted(_invoice(grand_total=Decimal("500"))),
        frontier_result=_extracted(_invoice()),
    )

    result = await graph.ainvoke(_initial_state())

    assert result["attempt"] == "frontier"
    assert result["reconciliation_issues"] == []
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True


@pytest.mark.anyio
async def test_reconciliation_failure_persists_after_frontier_retry_goes_to_human_review(
    no_real_ledger,
):
    bad_invoice = _invoice(grand_total=Decimal("500"))
    graph, _, _ = _build(
        specialist_result=_extracted(bad_invoice),
        frontier_result=_extracted(bad_invoice),
    )

    result = await graph.ainvoke(_initial_state())

    assert result["attempt"] == "frontier"
    assert len(result["reconciliation_issues"]) == 1
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    reasons = no_real_ledger[0]["review_reason"]
    assert any("Grand total computation" in r["message"] for r in reasons)


@pytest.mark.anyio
async def test_duplicate_after_frontier_fallback_goes_to_human_review(
    monkeypatch, no_real_ledger
):
    graph, _, _ = _build(
        specialist_result=_failed("Pydantic Validation error: not valid json"),
        frontier_result=_extracted(_invoice()),
    )

    async def _dup(session, invoice_number, vendor_name):
        return MagicMock(id=42)

    monkeypatch.setattr(nodes, "find_duplicate", _dup)

    result = await graph.ainvoke(_initial_state())

    assert result["attempt"] == "frontier"
    assert any(
        issue.category == "duplicate" for issue in result["reconciliation_issues"]
    )
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    reasons = no_real_ledger[0]["review_reason"]
    assert any(r["category"] == "duplicate" for r in reasons)


@pytest.mark.anyio
async def test_ledger_write_returns_entry_id_in_state(no_real_ledger):
    graph, _, _ = _build(specialist_result=_extracted(_invoice()))

    result = await graph.ainvoke(_initial_state())

    assert result["ledger_entry_id"] == 1


@pytest.mark.anyio
async def test_review_retry_feeds_reconciliation_issues_back_to_frontier(
    no_real_ledger,
):
    graph, _, frontier = _build(
        specialist_result=_extracted(_invoice(grand_total=Decimal("500"))),
        frontier_result=_extracted(_invoice()),
    )

    await graph.ainvoke(_initial_state())

    assert len(frontier.calls) == 1
    extra_context = frontier.calls[0]["extra_context"]
    assert extra_context is not None
    assert "Grand total computation" in extra_context


@pytest.mark.anyio
async def test_failed_review_retry_keeps_earlier_invoice_for_human_review(
    no_real_ledger,
):
    """A failed review retry must not discard the extraction it was retrying.

    The node only overwrites `invoice` when the retry produced one, so the
    entry still reaches the ledger flagged for review instead of routing to
    total_failure and being dropped.
    """
    bad_invoice = _invoice(grand_total=Decimal("500"))
    graph, _, _ = _build(
        specialist_result=_extracted(bad_invoice),
        frontier_result=_failed("Frontier structured output error: frontier boom"),
    )

    result = await graph.ainvoke(_initial_state())

    assert result["invoice"] is bad_invoice
    assert result["attempt"] == "frontier"
    assert len(no_real_ledger) == 1
    assert no_real_ledger[0]["needs_review"] is True
    assert no_real_ledger[0]["invoice"] is bad_invoice
