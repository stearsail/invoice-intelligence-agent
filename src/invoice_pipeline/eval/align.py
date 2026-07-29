from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from scipy.optimize import linear_sum_assignment

from invoice_pipeline.eval.compare import anls
from invoice_pipeline.schema import LineItem

MAX_MATCH_COST = 0.5


@dataclass(frozen=True)
class LineItemAlignment:
    matched: list[tuple[LineItem, LineItem]]
    hallucinated: list[LineItem]
    missing: list[LineItem]


def _numeric_distance(pred: Decimal | None, gold: Decimal | None) -> float:
    if pred is None and gold is None:
        return 0.0
    if pred is None or gold is None:
        return 1.0
    denominator = abs(gold) if gold != 0 else Decimal("1")
    return min(float(abs(pred - gold) / denominator), 1.0)


def _line_item_cost(pred: LineItem, gold: LineItem) -> float:
    description_cost = 1 - anls(pred.description, gold.description)
    unit_price_cost = _numeric_distance(pred.unit_price, gold.unit_price)
    quantity_cost = _numeric_distance(pred.quantity, gold.quantity)
    line_total_cost = _numeric_distance(pred.line_total, gold.line_total)
    return (description_cost + unit_price_cost + quantity_cost + line_total_cost) / 4


def align_line_items(
    pred_items: list[LineItem], gold_items: list[LineItem]
) -> LineItemAlignment:
    if not pred_items or not gold_items:
        return LineItemAlignment(
            matched=[], hallucinated=list(pred_items), missing=list(gold_items)
        )

    cost_matrix = np.array(
        [[_line_item_cost(pred, gold) for gold in gold_items] for pred in pred_items]
    )
    pred_indices, gold_indices = linear_sum_assignment(cost_matrix)

    matched: list[tuple[LineItem, LineItem]] = []
    matched_pred_indices: set[int] = set()
    matched_gold_indices: set[int] = set()
    for pred_index, gold_index in zip(pred_indices, gold_indices):
        if cost_matrix[pred_index, gold_index] <= MAX_MATCH_COST:
            matched.append((pred_items[pred_index], gold_items[gold_index]))
            matched_pred_indices.add(int(pred_index))
            matched_gold_indices.add(int(gold_index))

    hallucinated = [
        item for i, item in enumerate(pred_items) if i not in matched_pred_indices
    ]
    missing = [
        item for i, item in enumerate(gold_items) if i not in matched_gold_indices
    ]

    return LineItemAlignment(
        matched=matched, hallucinated=hallucinated, missing=missing
    )
