from decimal import Decimal
import re

# Prices appear as '20.000', '20,000', '20.000,00' or plain '20000'.
_PRICE_RE = re.compile(r"-?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d{1,2})?")


def parse_price(price: str | None) -> Decimal | None:
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
