from decimal import Decimal
from typing import Literal

PresenceLabel = Literal["tp", "fp", "fn", "tn"]


def exact_match(pred: object, gold: object) -> bool:
    return pred == gold


def numeric_match(
    pred: Decimal | None, gold: Decimal | None, tolerance: Decimal = Decimal("0.01")
) -> bool:
    if pred is None or gold is None:
        return pred == gold
    return abs(pred - gold) <= tolerance


def presence_match(pred: object, gold: object) -> PresenceLabel:
    pred_present = pred is not None
    gold_present = gold is not None
    if pred_present and gold_present:
        return "tp"
    if pred_present:
        return "fp"
    if gold_present:
        return "fn"
    return "tn"


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            substitute_cost = previous_row[j - 1] + (char_a != char_b)
            current_row.append(min(insert_cost, delete_cost, substitute_cost))
        previous_row = current_row
    return previous_row[-1]


def anls(pred: str | None, gold: str | None, threshold: float = 0.5) -> float:
    if pred is None and gold is None:
        return 1.0
    if pred is None or gold is None:
        return 0.0

    pred_norm = pred.strip().lower()
    gold_norm = gold.strip().lower()
    longest_len = max(len(pred_norm), len(gold_norm))
    if longest_len == 0:
        return 1.0

    similarity = 1 - _levenshtein(pred_norm, gold_norm) / longest_len
    return similarity if similarity >= threshold else 0.0
