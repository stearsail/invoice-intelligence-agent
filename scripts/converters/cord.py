import re
from invoice_pipeline.schema import Invoice, LineItem
from decimal import Decimal


def _menu_items(obj: dict) -> list[dict]:
    menu = obj.get("menu")
    if menu is None:
        return []
    if isinstance(menu, dict):
        return [menu]
    return menu


_QUANTITY_RE = re.compile(r"[a-zA-Z\s]*(\d+(?:\.\d+)?)[a-zA-Z\s]*")


def _parse_quantity(quantity: str | None) -> Decimal | None:
    if not isinstance(quantity, str):
        return None
    match = _QUANTITY_RE.fullmatch(quantity.strip())
    if match is None:
        return None
    return Decimal(match.group(1))


# Prices appear as '20.000', '20,000', '20.000,00' or plain '8000'.
_PRICE_RE = re.compile(r"(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d{1,2})?")


def _parse_price(price: str | None) -> Decimal | None:
    if not isinstance(price, str):
        return None
    cleaned = price.strip()
    if _PRICE_RE.fullmatch(cleaned) is None:
        return None
    last_sep = max(cleaned.rfind("."), cleaned.rfind(","))
    if last_sep == -1:
        return Decimal(cleaned)
    fraction = cleaned[last_sep + 1 :]
    if len(fraction) == 3:
        return Decimal(cleaned.replace(".", "").replace(",", ""))
    integer_part = cleaned[:last_sep].replace(".", "").replace(",", "")
    return Decimal(integer_part + "." + fraction)


def _sub_total_section(obj: dict) -> dict:
    sub_total = obj.get("sub_total")
    if sub_total is None:
        return {}
    if isinstance(sub_total, list):
        return sub_total[0] if sub_total else {}
    return sub_total


def _parse_amount(value: str | list[str] | None) -> Decimal | None:
    if isinstance(value, list):
        parts = [_parse_price(v) for v in value]
        present = [p for p in parts if p is not None]
        return present[0] if present else None
    return _parse_price(value)


# drop sign for negative discount values (-5.400)
def _drop_sign(value: str | list[str] | None) -> str | list[str] | None:
    if isinstance(value, list):
        return [_drop_sign(v) for v in value]
    if isinstance(value, str):
        return value.strip().removeprefix("-")
    return value


def convert_example(gt_parse: dict) -> Invoice:

    total_price = _parse_price((gt_parse.get("total") or {}).get("total_price"))

    sub_total = _sub_total_section(gt_parse)
    subtotal = _parse_amount(sub_total.get("subtotal_price"))
    tax = _parse_amount(sub_total.get("tax_price"))
    service_charge = _parse_amount(sub_total.get("service_price"))
    discount = _parse_amount(_drop_sign(sub_total.get("discount_price")))
    menu = _menu_items(gt_parse)
    line_items = []
    for item in menu:
        li_desc = item.get("nm")
        raw_li_quantity = item.get("cnt")
        raw_li_unit_price = item.get("unitprice")
        raw_li_total_price = item.get("price")

        li_quantity = _parse_quantity(raw_li_quantity)
        li_unit_price = _parse_price(raw_li_unit_price)
        li_total_price = _parse_price(raw_li_total_price)

        li = LineItem(
            description=li_desc,
            unit_price=li_unit_price,
            quantity=li_quantity,
            line_total=li_total_price,
        )
        line_items.append(li)
    return Invoice(
        document_type="receipt",
        currency="IDR",
        line_items=line_items,
        grand_total=total_price,
        subtotal=subtotal,
        tax=tax,
        service_charge=service_charge,
        discount=discount,
    )
