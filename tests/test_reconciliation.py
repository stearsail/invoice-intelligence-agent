from decimal import Decimal

from invoice_pipeline.reconciliation import reconcile
from invoice_pipeline.schema import Invoice, LineItem


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
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert issues[0].category == "unverifiable"
    assert issues[0].message == "Missing subtotal"


def test_no_line_items_is_unverifiable():
    invoice = _invoice(line_items=[])
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert issues[0].category == "unverifiable"
    assert issues[0].message == "No line items"


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
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert issues[0].category == "unverifiable"
    assert issues[0].message == "Missing line total for line 1"


def test_missing_line_total_index_is_one_based():
    invoice = _invoice(
        line_items=[
            LineItem(
                description="Item A",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            ),
            LineItem(
                description="Item B",
                quantity=Decimal("1"),
                unit_price=Decimal("50"),
                line_total=None,
            ),
        ]
    )
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert issues[0].message == "Missing line total for line 2"


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
    assert issues[0].category == "mismatch"
    assert "Line items sum to 50" in issues[0].message
    assert "Subtotal is 100" in issues[0].message


def test_grand_total_not_matching_is_flagged():
    invoice = _invoice(grand_total=Decimal("500"))
    issues = reconcile(invoice)
    assert len(issues) == 1
    assert issues[0].category == "mismatch"
    assert "Grand total computation: 110" in issues[0].message
    assert "not 500" in issues[0].message


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
