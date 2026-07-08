from decimal import Decimal
from invoice_agent.schema import Invoice


def reconcile(invoice: Invoice) -> list[str]:
    issues = []
    if invoice.subtotal is None:
        issues.append("unverifiable: missing subtotal")
        return issues

    if not invoice.line_items:
        issues.append("unverifiable: no line items")
        return issues

    for i, item in enumerate(invoice.line_items):
        if item.line_total is None:
            issues.append(f"unverifiable: missing line total for line {i}")
    if issues:
        return issues

    items_total = sum(item.line_total for item in invoice.line_items)
    tolerance = invoice.subtotal * Decimal("0.01")

    if abs(items_total - invoice.subtotal) > tolerance:
        issues.append(
            f"line items sum to {items_total} but subtotal is {invoice.subtotal} "
            f"(difference: {abs(items_total - invoice.subtotal)})"
        )

    total = (
        invoice.subtotal
        + (invoice.tax or Decimal("0"))
        + (invoice.service_charge or Decimal("0"))
        - (invoice.discount or Decimal("0"))
    )
    tolerance = invoice.grand_total * Decimal("0.01")

    if abs(total - invoice.grand_total) > tolerance:
        issues.append(
            f"grand total computation is {total} but grand total is {invoice.grand_total} "
            f"(difference: {abs(total - invoice.grand_total)})"
        )

    return issues
