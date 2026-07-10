from decimal import Decimal

from invoice_agent.reconciliation import reconcile
from invoice_agent.schema import Invoice, LineItem


def _invoice(**overrides) -> Invoice:
    defaults = {
        "document_type": "receipt",
        "currency": "USD",
        "grand_total": Decimal("110"),
        "subtotal": Decimal("100"),
        "tax": Decimal("10"),
        "line_items": [
            LineItem(
                description="Item A",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            ),
        ],
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def test_reconciles_when_everything_matches():
    assert reconcile(_invoice()) == []


def test_missing_subtotal_is_unverifiable():
    invoice = _invoice(subtotal=None)
    assert reconcile(invoice) == ["unverifiable: missing subtotal"]


def test_no_line_items_is_unverifiable():
    invoice = _invoice(line_items=[])
    assert reconcile(invoice) == ["unverifiable: no line items"]


def test_missing_line_total_is_unverifiable_and_skips_math():
    invoice = _invoice(
        line_items=[
            LineItem(
                description="Item A",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=None,
            ),
        ]
    )
    assert reconcile(invoice) == ["unverifiable: missing line total for line 0"]


def test_line_items_not_matching_subtotal_is_flagged():
    invoice = _invoice(
        line_items=[
            LineItem(
                description="Item A",
                quantity=Decimal("1"),
                unit_price=Decimal("50"),
                line_total=Decimal("50"),
            ),
        ],
    )
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert "line items sum to 50" in issues[0]
    assert "subtotal is 100" in issues[0]


def test_grand_total_not_matching_is_flagged():
    invoice = _invoice(grand_total=Decimal("500"))
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert "grand total computation is 110" in issues[0]
    assert "grand total is 500" in issues[0]


def test_small_rounding_difference_within_tolerance_passes():
    invoice = _invoice(grand_total=Decimal("110.50"))
    assert reconcile(invoice) == []


def test_both_checks_can_fail_independently():
    invoice = _invoice(
        line_items=[
            LineItem(
                description="Item A",
                quantity=Decimal("1"),
                unit_price=Decimal("50"),
                line_total=Decimal("50"),
            ),
        ],
        grand_total=Decimal("500"),
    )
    assert len(reconcile(invoice)) == 2
