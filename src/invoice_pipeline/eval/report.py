from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from invoice_pipeline.eval.align import align_line_items
from invoice_pipeline.eval.compare import (
    anls,
    exact_match,
    numeric_match,
    presence_match,
)
from invoice_pipeline.eval.metrics import (
    AccuracyCounts,
    FieldCounts,
    accuracy,
    field_f1,
    macro_f1,
    micro_f1,
    precision,
    recall,
)
from invoice_pipeline.schema import Invoice, Party

T = TypeVar("T")


@dataclass
class EvaluationAccumulator:
    accuracy_fields: dict[str, AccuracyCounts] = field(default_factory=dict)
    field_counts: dict[str, FieldCounts] = field(default_factory=dict)


def _fuzzy_match(pred: str, gold: str) -> bool:
    return anls(pred, gold) > 0


def _score_required(acc: EvaluationAccumulator, name: str, is_correct: bool) -> None:
    acc.accuracy_fields.setdefault(name, AccuracyCounts()).add(is_correct)


def _score_nullable(
    acc: EvaluationAccumulator,
    name: str,
    pred_value: T | None,
    gold_value: T | None,
    matches: Callable[[T, T], bool],
) -> None:
    counts = acc.field_counts.setdefault(name, FieldCounts())
    label = presence_match(pred_value, gold_value)
    if label == "tp" and not matches(pred_value, gold_value):  # type: ignore[arg-type]
        counts.add("fp")
        counts.add("fn")
    else:
        counts.add(label)


def _score_party(
    acc: EvaluationAccumulator, prefix: str, pred: Party | None, gold: Party | None
) -> None:
    counts = acc.field_counts.setdefault(prefix, FieldCounts())
    label = presence_match(pred, gold)
    counts.add(label)
    if label != "tp" or pred is None or gold is None:
        return

    _score_nullable(acc, f"{prefix}.name", pred.name, gold.name, _fuzzy_match)
    _score_nullable(acc, f"{prefix}.address", pred.address, gold.address, _fuzzy_match)
    _score_nullable(acc, f"{prefix}.tax_id", pred.tax_id, gold.tax_id, _fuzzy_match)
    _score_nullable(acc, f"{prefix}.iban", pred.iban, gold.iban, _fuzzy_match)


def score_invoice(acc: EvaluationAccumulator, pred: Invoice, gold: Invoice) -> None:
    _score_required(
        acc, "document_type", exact_match(pred.document_type, gold.document_type)
    )
    _score_required(acc, "currency", exact_match(pred.currency, gold.currency))
    _score_required(
        acc, "grand_total", numeric_match(pred.grand_total, gold.grand_total)
    )

    _score_nullable(
        acc, "invoice_number", pred.invoice_number, gold.invoice_number, _fuzzy_match
    )
    _score_nullable(acc, "issue_date", pred.issue_date, gold.issue_date, exact_match)
    _score_nullable(acc, "due_date", pred.due_date, gold.due_date, exact_match)
    _score_nullable(acc, "subtotal", pred.subtotal, gold.subtotal, numeric_match)
    _score_nullable(acc, "tax", pred.tax, gold.tax, numeric_match)
    _score_nullable(
        acc, "service_charge", pred.service_charge, gold.service_charge, numeric_match
    )
    _score_nullable(acc, "discount", pred.discount, gold.discount, numeric_match)

    _score_party(acc, "vendor", pred.vendor, gold.vendor)
    _score_party(acc, "customer", pred.customer, gold.customer)

    alignment = align_line_items(pred.line_items, gold.line_items)
    line_item_counts = acc.field_counts.setdefault("line_items", FieldCounts())
    for _ in alignment.matched:
        line_item_counts.add("tp")
    for _ in alignment.hallucinated:
        line_item_counts.add("fp")
    for _ in alignment.missing:
        line_item_counts.add("fn")

    for pred_item, gold_item in alignment.matched:
        _score_nullable(
            acc,
            "line_items.description",
            pred_item.description,
            gold_item.description,
            _fuzzy_match,
        )
        _score_nullable(
            acc,
            "line_items.unit_price",
            pred_item.unit_price,
            gold_item.unit_price,
            numeric_match,
        )
        _score_nullable(
            acc,
            "line_items.quantity",
            pred_item.quantity,
            gold_item.quantity,
            numeric_match,
        )
        _score_nullable(
            acc,
            "line_items.line_total",
            pred_item.line_total,
            gold_item.line_total,
            numeric_match,
        )


@dataclass
class FieldReport:
    name: str
    metric: Literal["accuracy", "precision_recall_f1"]
    support: int
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


def summarize(acc: EvaluationAccumulator) -> list[FieldReport]:
    reports = [
        FieldReport(
            name=name,
            metric="accuracy",
            support=counts.total,
            accuracy=accuracy(counts.correct, counts.total),
        )
        for name, counts in acc.accuracy_fields.items()
    ]
    reports += [
        FieldReport(
            name=name,
            metric="precision_recall_f1",
            support=counts.tp + counts.fp + counts.fn,
            precision=precision(counts.tp, counts.fp),
            recall=recall(counts.tp, counts.fn),
            f1=field_f1(counts),
        )
        for name, counts in acc.field_counts.items()
    ]
    return reports


def overall_scores(acc: EvaluationAccumulator) -> dict[str, float]:
    counts = list(acc.field_counts.values())
    return {"macro_f1": macro_f1(counts), "micro_f1": micro_f1(counts)}
