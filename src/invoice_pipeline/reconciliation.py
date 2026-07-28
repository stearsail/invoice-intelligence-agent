from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from invoice_pipeline.schema import Invoice


class ReconciliationIssue(BaseModel):
    category: Literal["unverifiable", "mismatch", "duplicate"]
    message: str


_ROUNDING_TOLERANCE_PER_ITEM = Decimal("0.01")


def reconcile(invoice: Invoice) -> list[ReconciliationIssue]:
    issues = []
    if invoice.subtotal is None:
        issues.append(
            ReconciliationIssue(category="unverifiable", message="Missing subtotal")
        )
        return issues

    if not invoice.line_items:
        issues.append(
            ReconciliationIssue(category="unverifiable", message="No line items")
        )
        return issues

    for i, item in enumerate(invoice.line_items):
        if item.line_total is None:
            issues.append(
                ReconciliationIssue(
                    category="unverifiable",
                    message=f"Missing line total for line {i + 1}",
                )
            )
    if issues:
        return issues

    items_total = sum(item.line_total for item in invoice.line_items)
    tolerance = _ROUNDING_TOLERANCE_PER_ITEM * len(invoice.line_items)

    if abs(items_total - invoice.subtotal) > tolerance:
        issues.append(
            ReconciliationIssue(
                category="mismatch",
                message=f"Line items sum to {items_total}. Subtotal is {invoice.subtotal} (Difference: {abs(items_total - invoice.subtotal)})",
            )
        )

    total = (
        invoice.subtotal
        + (invoice.tax or Decimal("0"))
        + (invoice.service_charge or Decimal("0"))
        - (invoice.discount or Decimal("0"))
    )
    # +1 for this recombination step itself, on top of whatever rounding
    # drift the line items already carried into subtotal.
    tolerance = _ROUNDING_TOLERANCE_PER_ITEM * (len(invoice.line_items) + 1)

    if abs(total - invoice.grand_total) > tolerance:
        issues.append(
            ReconciliationIssue(
                category="mismatch",
                message=f"Grand total computation: {total} (not {invoice.grand_total} — difference: {abs(total - invoice.grand_total)})",
            )
        )
    return issues
