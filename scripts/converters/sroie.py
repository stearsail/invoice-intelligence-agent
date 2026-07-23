import re
from datetime import datetime, date
from decimal import Decimal
from invoice_agent.schema import Invoice, Party

_TAG_RE = re.compile(r"<s_(\w+)>(.*?)</s_\1>", re.DOTALL)


def _parse_tags(text: str) -> dict[str, str]:
    return {tag: value.strip() for tag, value in _TAG_RE.findall(text)}


_PRICE_RE = re.compile(r"(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d{1,2})?")


def _parse_price(price: str | None) -> Decimal | None:
    if not price:
        return None
    cleaned = price.strip().lstrip("$RM").strip()
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


# Real SROIE receipts print dates in inconsistent formats depending on the till.
_DATE_FORMATS = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%b %d, %Y",
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


def convert_example(text: str) -> Invoice:
    fields = _parse_tags(text)

    company = fields.get("company")
    address = fields.get("address")
    vendor = Party(name=company, address=address) if company else None

    return Invoice(
        document_type="receipt",
        vendor=vendor,
        currency="MYR",
        line_items=[],
        grand_total=_parse_price(fields.get("total")),
        issue_date=_parse_date(fields.get("date")),
    )
