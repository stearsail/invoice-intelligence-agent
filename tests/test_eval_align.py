from decimal import Decimal

from invoice_pipeline.eval.align import align_line_items
from invoice_pipeline.schema import LineItem


def _item(
    description: str, unit_price: str, quantity: str, line_total: str
) -> LineItem:
    return LineItem(
        description=description,
        unit_price=Decimal(unit_price),
        quantity=Decimal(quantity),
        line_total=Decimal(line_total),
    )


def test_identical_items_all_match():
    items = [_item("Widget", "10.00", "2", "20.00")]
    result = align_line_items(items, items)
    assert len(result.matched) == 1
    assert result.hallucinated == []
    assert result.missing == []


def test_reordered_items_still_match_correctly():
    pred = [
        _item("Widget B", "5.00", "1", "5.00"),
        _item("Widget A", "10.00", "2", "20.00"),
    ]
    gold = [
        _item("Widget A", "10.00", "2", "20.00"),
        _item("Widget B", "5.00", "1", "5.00"),
    ]
    result = align_line_items(pred, gold)
    assert len(result.matched) == 2
    matched_descriptions = {(p.description, g.description) for p, g in result.matched}
    assert matched_descriptions == {("Widget B", "Widget B"), ("Widget A", "Widget A")}
    assert result.hallucinated == []
    assert result.missing == []


def test_extra_predicted_item_is_hallucinated():
    pred = [
        _item("Widget A", "10.00", "2", "20.00"),
        _item("Widget B", "5.00", "1", "5.00"),
    ]
    gold = [_item("Widget A", "10.00", "2", "20.00")]
    result = align_line_items(pred, gold)
    assert len(result.matched) == 1
    assert len(result.hallucinated) == 1
    assert result.hallucinated[0].description == "Widget B"
    assert result.missing == []


def test_missing_predicted_item_is_flagged_missing():
    pred = [_item("Widget A", "10.00", "2", "20.00")]
    gold = [
        _item("Widget A", "10.00", "2", "20.00"),
        _item("Widget B", "5.00", "1", "5.00"),
    ]
    result = align_line_items(pred, gold)
    assert len(result.matched) == 1
    assert result.hallucinated == []
    assert len(result.missing) == 1
    assert result.missing[0].description == "Widget B"


def test_unrelated_items_are_not_forced_to_match():
    pred = [_item("Completely Different Product", "999.00", "50", "49950.00")]
    gold = [_item("Widget A", "10.00", "2", "20.00")]
    result = align_line_items(pred, gold)
    assert result.matched == []
    assert len(result.hallucinated) == 1
    assert len(result.missing) == 1


def test_no_predicted_items_marks_all_gold_as_missing():
    gold = [_item("Widget A", "10.00", "2", "20.00")]
    result = align_line_items([], gold)
    assert result.matched == []
    assert result.hallucinated == []
    assert result.missing == gold


def test_no_gold_items_marks_all_predicted_as_hallucinated():
    pred = [_item("Widget A", "10.00", "2", "20.00")]
    result = align_line_items(pred, [])
    assert result.matched == []
    assert result.hallucinated == pred
    assert result.missing == []


def test_both_empty_produces_empty_alignment():
    result = align_line_items([], [])
    assert result.matched == []
    assert result.hallucinated == []
    assert result.missing == []
