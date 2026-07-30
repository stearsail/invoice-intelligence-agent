from decimal import Decimal

from invoice_pipeline.eval.report import (
    EvaluationAccumulator,
    filtered_scores,
    overall_scores,
    score_invoice,
    summarize,
)
from invoice_pipeline.schema import Invoice, LineItem, Party


def _invoice(**overrides) -> Invoice:
    defaults = {
        "document_type": "invoice",
        "currency": "USD",
        "grand_total": Decimal("120.00"),
        "subtotal": Decimal("100.00"),
        "tax": Decimal("20.00"),
        "invoice_number": "INV-001",
        "vendor": Party(name="Brooks LLC", address="123 Main St"),
        "customer": Party(name="Jane Doe"),
        "line_items": [
            LineItem(
                description="Widget",
                unit_price=Decimal("50.00"),
                quantity=Decimal("2"),
                line_total=Decimal("100.00"),
            ),
        ],
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def test_identical_invoices_score_perfectly():
    acc = EvaluationAccumulator()
    invoice = _invoice()
    score_invoice(acc, invoice, invoice)

    assert all(
        counts.correct == counts.total for counts in acc.accuracy_fields.values()
    )
    assert all(
        counts.fp == 0 and counts.fn == 0 for counts in acc.field_counts.values()
    )
    assert overall_scores(acc) == {"macro_f1": 1.0, "micro_f1": 1.0}


def test_required_field_mismatch_lowers_accuracy():
    acc = EvaluationAccumulator()
    pred = _invoice(document_type="receipt")
    gold = _invoice(document_type="invoice")
    score_invoice(acc, pred, gold)
    assert acc.accuracy_fields["document_type"].correct == 0
    assert acc.accuracy_fields["document_type"].total == 1


def test_nullable_field_hallucination_is_false_positive():
    acc = EvaluationAccumulator()
    pred = _invoice(due_date="2024-01-01")
    gold = _invoice(due_date=None)
    score_invoice(acc, pred, gold)
    assert acc.field_counts["due_date"].fp == 1
    assert acc.field_counts["due_date"].fn == 0


def test_nullable_field_miss_is_false_negative():
    acc = EvaluationAccumulator()
    pred = _invoice(due_date=None)
    gold = _invoice(due_date="2024-01-01")
    score_invoice(acc, pred, gold)
    assert acc.field_counts["due_date"].fn == 1
    assert acc.field_counts["due_date"].fp == 0


def test_nullable_field_present_but_wrong_counts_as_both_fp_and_fn():
    acc = EvaluationAccumulator()
    pred = _invoice(invoice_number="INV-001")
    gold = _invoice(invoice_number="COMPLETELY-DIFFERENT-CODE-999")
    score_invoice(acc, pred, gold)
    assert acc.field_counts["invoice_number"].fp == 1
    assert acc.field_counts["invoice_number"].fn == 1
    assert acc.field_counts["invoice_number"].tp == 0


def test_vendor_absent_on_both_sides_is_true_negative_and_skips_subfields():
    acc = EvaluationAccumulator()
    pred = _invoice(vendor=None)
    gold = _invoice(vendor=None)
    score_invoice(acc, pred, gold)
    assert acc.field_counts["vendor"].tn == 1
    assert "vendor.name" not in acc.field_counts


def test_vendor_hallucinated_does_not_score_subfields():
    acc = EvaluationAccumulator()
    pred = _invoice(vendor=Party(name="Made Up Vendor"))
    gold = _invoice(vendor=None)
    score_invoice(acc, pred, gold)
    assert acc.field_counts["vendor"].fp == 1
    assert "vendor.name" not in acc.field_counts


def test_vendor_present_on_both_sides_scores_subfields():
    acc = EvaluationAccumulator()
    pred = _invoice(vendor=Party(name="Totally Wrong Name Here"))
    gold = _invoice(vendor=Party(name="Brooks LLC"))
    score_invoice(acc, pred, gold)
    assert acc.field_counts["vendor"].tp == 1
    assert acc.field_counts["vendor.name"].fp == 1
    assert acc.field_counts["vendor.name"].fn == 1


def test_line_items_hallucination_does_not_score_subfields():
    acc = EvaluationAccumulator()
    pred = _invoice(
        line_items=[
            LineItem(
                description="Widget",
                unit_price=Decimal("50.00"),
                quantity=Decimal("2"),
                line_total=Decimal("100.00"),
            ),
            LineItem(
                description="Extra hallucinated item",
                unit_price=Decimal("999.00"),
                quantity=Decimal("1"),
                line_total=Decimal("999.00"),
            ),
        ]
    )
    gold = _invoice()
    score_invoice(acc, pred, gold)
    assert acc.field_counts["line_items"].tp == 1
    assert acc.field_counts["line_items"].fp == 1
    assert acc.field_counts["line_items.description"].tp == 1
    assert acc.field_counts["line_items.description"].fp == 0


def test_summarize_reports_both_accuracy_and_precision_recall_fields():
    acc = EvaluationAccumulator()
    score_invoice(acc, _invoice(), _invoice())
    reports = summarize(acc)
    by_name = {report.name: report for report in reports}
    assert by_name["document_type"].metric == "accuracy"
    assert by_name["document_type"].accuracy == 1.0
    assert by_name["invoice_number"].metric == "precision_recall_f1"
    assert by_name["invoice_number"].f1 == 1.0


def test_filtered_scores_restricts_to_requested_fields():
    acc = EvaluationAccumulator()
    pred = _invoice(invoice_number="INV-001", due_date=None)
    gold = _invoice(invoice_number="INV-001", due_date="2024-01-01")
    score_invoice(acc, pred, gold)

    full = overall_scores(acc)
    invoice_number_only = filtered_scores(acc, ["invoice_number"])

    assert invoice_number_only == {"macro_f1": 1.0, "micro_f1": 1.0}
    assert full["macro_f1"] < 1.0


def test_filtered_scores_ignores_unknown_field_names():
    acc = EvaluationAccumulator()
    score_invoice(acc, _invoice(), _invoice())

    result = filtered_scores(acc, ["invoice_number", "not_a_real_field"])

    assert result == {"macro_f1": 1.0, "micro_f1": 1.0}


def test_filtered_scores_empty_selection_is_vacuously_perfect():
    acc = EvaluationAccumulator()
    score_invoice(acc, _invoice(), _invoice())

    assert filtered_scores(acc, []) == {"macro_f1": 1.0, "micro_f1": 1.0}
