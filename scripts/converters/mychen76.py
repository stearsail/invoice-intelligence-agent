import ast
import json
import re
from datetime import datetime, date
from decimal import Decimal
from invoice_agent.schema import Invoice, Party, LineItem


def _parse_annotation(parsed_data: str) -> dict:
    outer = json.loads(parsed_data)
    # The "json" field is a Python dict repr (single-quoted), not valid JSON.
    return ast.literal_eval(outer["json"])


# Thousands may be grouped with spaces, dots, or commas; matched loosely and
# then disambiguated below, since some fields also contain junk around the
# actual number (e.g. "Total:82.20", "$89.09 $89.09", "48.65 48.65EUR").
_PRICE_RE = re.compile(r"\d{1,3}(?:[ .,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?")


def _parse_price(price: str | None) -> Decimal | None:
    if not price:
        return None
    cleaned = price.strip().replace("$", "")
    match = _PRICE_RE.search(cleaned)
    if match is None:
        return None
    matched = match.group(0)
    last_sep = max(matched.rfind("."), matched.rfind(","), matched.rfind(" "))
    if last_sep == -1:
        return Decimal(matched)
    fraction = matched[last_sep + 1 :]
    if len(fraction) == 3:
        return Decimal(re.sub(r"[ .,]", "", matched))
    integer_part = re.sub(r"[ .,]", "", matched[:last_sep])
    return Decimal(integer_part + "." + fraction)


# Real-world receipts here come from several locales, hence the format spread.
_DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d-%m-%Y",
)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _find_first(obj, *keys: str):
    """Search a nested dict/list structure for the first occurrence of any of
    `keys`, at any depth. Annotations in this dataset aren't consistently
    shaped — some are flat, some nest fields under header/items/summary, some
    merge summary fields into the last line item, and receipts use an
    entirely different set of field names than invoices — so a fixed path
    can't be trusted."""
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key]:
                return obj[key]
        for value in obj.values():
            found = _find_first(value, *keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, *keys)
            if found is not None:
                return found
    return None


def _extract_items(annotation: dict) -> list[dict]:
    items = annotation.get("items") or annotation.get("line_items")
    if isinstance(items, list) and items:
        return items
    if isinstance(items, dict):
        return [items]
    # Some annotations have no items wrapper at all — a single item's fields
    # sit directly on the annotation itself.
    if any(
        k in annotation
        for k in ("item_desc", "item_qty", "item_net_price", "item_gross_worth")
    ):
        return [annotation]
    return []


def _item_description(item: dict) -> str | None:
    return item.get("item_desc") or item.get("item_name")


def _item_unit_price(item: dict) -> Decimal | None:
    return _parse_price(item.get("item_net_price"))


def _item_quantity(item: dict) -> Decimal | None:
    return _parse_price(item.get("item_qty") or item.get("item_quantity"))


def _item_total(item: dict) -> Decimal | None:
    # item_net_worth (pre-tax) is what actually sums to the invoice's
    # subtotal — item_gross_worth includes per-line VAT, which would double
    # count tax once summed against a pre-tax subtotal. Receipts (item_value)
    # have no separate net/gross split to begin with.
    return _parse_price(item.get("item_net_worth") or item.get("item_value"))


def _grand_total(annotation: dict) -> Decimal | None:
    total = _parse_price(_find_first(annotation, "total_gross_worth", "total"))
    if total is not None:
        return total
    # Some rows have a corrupted total (e.g. literally the string "Total")
    # but valid net worth + VAT, from which the real total is reconstructible.
    net = _parse_price(_find_first(annotation, "total_net_worth", "subtotal"))
    vat = _parse_price(_find_first(annotation, "total_vat", "tax"))
    if net is not None and vat is not None:
        return net + vat
    return None


def convert_example(parsed_data: str) -> Invoice:
    annotation = _parse_annotation(parsed_data)

    seller = _find_first(annotation, "seller")
    store_name = _find_first(annotation, "store_name")
    client = _find_first(annotation, "client")

    if seller:
        vendor = Party(
            name=seller,
            tax_id=_find_first(annotation, "seller_tax_id"),
            iban=_find_first(annotation, "iban"),
        )
        document_type = "invoice"
    elif store_name:
        vendor = Party(name=store_name, address=_find_first(annotation, "store_addr"))
        document_type = "receipt"
    else:
        vendor = None
        document_type = "receipt"

    customer = (
        Party(name=client, tax_id=_find_first(annotation, "client_tax_id"))
        if client
        else None
    )

    line_items = [
        LineItem(
            description=_item_description(item),
            unit_price=_item_unit_price(item),
            quantity=_item_quantity(item),
            line_total=_item_total(item),
        )
        for item in _extract_items(annotation)
    ]

    return Invoice(
        document_type=document_type,
        vendor=vendor,
        customer=customer,
        invoice_number=_find_first(annotation, "invoice_no"),
        issue_date=_parse_date(_find_first(annotation, "invoice_date", "date")),
        currency="USD",
        line_items=line_items,
        grand_total=_grand_total(annotation),
        subtotal=_parse_price(_find_first(annotation, "total_net_worth", "subtotal")),
        tax=_parse_price(_find_first(annotation, "total_vat", "tax")),
    )
