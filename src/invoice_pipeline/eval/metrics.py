from dataclasses import dataclass

from invoice_pipeline.eval.compare import PresenceLabel


@dataclass
class FieldCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def add(self, label: PresenceLabel) -> None:
        setattr(self, label, getattr(self, label) + 1)


@dataclass
class AccuracyCounts:
    correct: int = 0
    total: int = 0

    def add(self, is_correct: bool) -> None:
        self.total += 1
        if is_correct:
            self.correct += 1


def precision(tp: int, fp: int) -> float:
    if tp + fp == 0:
        return 1.0
    return tp / (tp + fp)


def recall(tp: int, fn: int) -> float:
    if tp + fn == 0:
        return 1.0
    return tp / (tp + fn)


def f1(precision_value: float, recall_value: float) -> float:
    if precision_value + recall_value == 0:
        return 0.0
    return 2 * precision_value * recall_value / (precision_value + recall_value)


def field_f1(counts: FieldCounts) -> float:
    return f1(precision(counts.tp, counts.fp), recall(counts.tp, counts.fn))


def accuracy(correct: int, total: int) -> float:
    if total == 0:
        return 1.0
    return correct / total


def macro_f1(field_counts: list[FieldCounts]) -> float:
    if not field_counts:
        return 1.0
    return sum(field_f1(counts) for counts in field_counts) / len(field_counts)


def micro_f1(field_counts: list[FieldCounts]) -> float:
    total_tp = sum(counts.tp for counts in field_counts)
    total_fp = sum(counts.fp for counts in field_counts)
    total_fn = sum(counts.fn for counts in field_counts)
    return f1(precision(total_tp, total_fp), recall(total_tp, total_fn))
