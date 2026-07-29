import pytest

from invoice_pipeline.eval.metrics import (
    AccuracyCounts,
    FieldCounts,
    accuracy,
    f1,
    field_f1,
    macro_f1,
    micro_f1,
    precision,
    recall,
)


def test_precision_normal_case():
    assert precision(tp=8, fp=2) == 0.8


def test_precision_no_positive_predictions_is_vacuously_perfect():
    assert precision(tp=0, fp=0) == 1.0


def test_recall_normal_case():
    assert recall(tp=8, fn=2) == 0.8


def test_recall_no_positive_labels_is_vacuously_perfect():
    assert recall(tp=0, fn=0) == 1.0


def test_f1_balances_precision_and_recall():
    assert f1(precision_value=0.8, recall_value=0.8) == pytest.approx(0.8)


def test_f1_both_zero_is_zero_not_a_division_error():
    assert f1(precision_value=0.0, recall_value=0.0) == 0.0


def test_f1_perfect_precision_and_recall_is_one():
    assert f1(precision_value=1.0, recall_value=1.0) == 1.0


def test_accuracy_normal_case():
    assert accuracy(correct=9, total=10) == 0.9


def test_accuracy_no_instances_is_vacuously_perfect():
    assert accuracy(correct=0, total=0) == 1.0


def test_accuracy_counts_add_tracks_correct_and_total():
    counts = AccuracyCounts()
    counts.add(True)
    counts.add(True)
    counts.add(False)
    assert counts == AccuracyCounts(correct=2, total=3)


def test_field_counts_add_increments_matching_bucket():
    counts = FieldCounts()
    counts.add("tp")
    counts.add("tp")
    counts.add("fp")
    counts.add("fn")
    counts.add("tn")
    assert counts == FieldCounts(tp=2, fp=1, fn=1, tn=1)


def test_field_f1_computes_from_counts():
    counts = FieldCounts(tp=8, fp=2, fn=2)
    assert field_f1(counts) == pytest.approx(0.8)


def test_macro_f1_averages_each_field_equally():
    perfect_field = FieldCounts(tp=1, fp=0, fn=0)
    broken_field = FieldCounts(tp=0, fp=0, fn=100)
    assert macro_f1([perfect_field, broken_field]) == 0.5


def test_macro_f1_empty_is_vacuously_perfect():
    assert macro_f1([]) == 1.0


def test_micro_f1_weights_by_volume_not_by_field_count():
    rare_perfect_field = FieldCounts(tp=1, fp=0, fn=0)
    common_broken_field = FieldCounts(tp=0, fp=0, fn=100)
    score = micro_f1([rare_perfect_field, common_broken_field])
    # pooled: tp=1, fp=0, fn=100 -> recall = 1/101, precision = 1.0 (no fp)
    assert score < 0.1


def test_macro_and_micro_can_disagree():
    rare_perfect_field = FieldCounts(tp=1, fp=0, fn=0)
    common_broken_field = FieldCounts(tp=0, fp=0, fn=100)
    macro = macro_f1([rare_perfect_field, common_broken_field])
    micro = micro_f1([rare_perfect_field, common_broken_field])
    assert macro > micro
