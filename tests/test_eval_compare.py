from decimal import Decimal

from invoice_pipeline.eval.compare import (
    anls,
    exact_match,
    numeric_match,
    presence_match,
)


def test_exact_match_identical_strings():
    assert exact_match("INV-001", "INV-001") is True


def test_exact_match_different_strings():
    assert exact_match("INV-001", "INV-002") is False


def test_exact_match_both_none():
    assert exact_match(None, None) is True


def test_numeric_match_identical():
    assert numeric_match(Decimal("100.00"), Decimal("100.00")) is True


def test_numeric_match_within_tolerance():
    assert numeric_match(Decimal("100.00"), Decimal("100.01")) is True


def test_numeric_match_at_tolerance_boundary():
    assert (
        numeric_match(Decimal("100.00"), Decimal("100.01"), tolerance=Decimal("0.01"))
        is True
    )


def test_numeric_match_outside_tolerance():
    assert numeric_match(Decimal("100.00"), Decimal("100.02")) is False


def test_numeric_match_both_none():
    assert numeric_match(None, None) is True


def test_numeric_match_pred_none_gold_present():
    assert numeric_match(None, Decimal("100.00")) is False


def test_numeric_match_pred_present_gold_none():
    assert numeric_match(Decimal("100.00"), None) is False


def test_presence_match_both_present_is_true_positive():
    assert presence_match("PO-123", "PO-123") == "tp"


def test_presence_match_hallucinated_is_false_positive():
    assert presence_match("PO-123", None) == "fp"


def test_presence_match_missed_is_false_negative():
    assert presence_match(None, "PO-123") == "fn"


def test_presence_match_both_absent_is_true_negative():
    assert presence_match(None, None) == "tn"


def test_anls_identical_strings_scores_one():
    assert anls("Brooks LLC", "Brooks LLC") == 1.0


def test_anls_is_case_and_whitespace_insensitive():
    assert anls(" brooks llc ", "Brooks LLC") == 1.0


def test_anls_minor_typo_scores_partial_credit():
    score = anls("Brooks LLC", "Brooks LLC.")
    assert 0.5 <= score < 1.0


def test_anls_unrelated_strings_scores_zero():
    assert anls("Brooks LLC", "Totally Different Vendor Name") == 0.0


def test_anls_both_none_scores_one():
    assert anls(None, None) == 1.0


def test_anls_one_none_scores_zero():
    assert anls("Brooks LLC", None) == 0.0


def test_anls_both_empty_strings_scores_one():
    assert anls("", "") == 1.0
