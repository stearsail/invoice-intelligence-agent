from decimal import Decimal

import pytest
from pydantic import ValidationError

from scripts.converters.cord import (
    _drop_sign,
    _menu_items,
    _parse_amount,
    _parse_price,
    _parse_quantity,
    _sub_total_section,
    convert_example,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("8000", Decimal("8000")),
        (" 8000 ", Decimal("8000")),
        ("20.000", Decimal("20000")),
        ("20,000", Decimal("20000")),
        ("1.234.567", Decimal("1234567")),
        ("20.000,00", Decimal("20000.00")),
        ("20.00", Decimal("20.00")),
        ("12,5", Decimal("12.5")),
        ("-5,400", None),
        ("Rp 20.000", None),
        ("abc", None),
    ],
)
def test_parse_price(raw, expected):
    assert _parse_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("2", Decimal("2")),
        ("2X", Decimal("2")),
        ("x 2", Decimal("2")),
        ("4.00xITEMs", Decimal("4.00")),
        ("1,000", None),
    ],
)
def test_parse_quantity(raw, expected):
    assert _parse_quantity(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("20.000", Decimal("20000")),
        ([], None),
        (["abc"], None),
        # Real CORD data: list-valued amounts are almost always a duplicated
        # reading of the SAME value, not components to add (e.g. real
        # example: subtotal_price == ["49.636", "49.636"]). Summing would
        # silently double the amount, so we take the first parseable value.
        (["10.000", "20.000"], Decimal("10000")),
        (["10.000", "abc"], Decimal("10000")),
        (["abc", "20.000"], Decimal("20000")),
    ],
)
def test_parse_amount(raw, expected):
    assert _parse_amount(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("-5,400", "5,400"),
        (" -5,400 ", "5,400"),
        ("5,400", "5,400"),
        (["-1.000", "2.000"], ["1.000", "2.000"]),
    ],
)
def test_drop_sign(raw, expected):
    assert _drop_sign(raw) == expected


def test_menu_items_missing():
    assert _menu_items({}) == []


def test_menu_items_single_dict():
    assert _menu_items({"menu": {"nm": "x"}}) == [{"nm": "x"}]


def test_menu_items_list():
    assert _menu_items({"menu": [{"nm": "x"}, {"nm": "y"}]}) == [
        {"nm": "x"},
        {"nm": "y"},
    ]


def test_sub_total_section_missing():
    assert _sub_total_section({}) == {}


def test_sub_total_section_dict():
    assert _sub_total_section({"sub_total": {"tax_price": "1"}}) == {"tax_price": "1"}


def test_sub_total_section_list_takes_first():
    assert _sub_total_section(
        {"sub_total": [{"tax_price": "1"}, {"tax_price": "2"}]}
    ) == {"tax_price": "1"}


def test_sub_total_section_empty_list():
    assert _sub_total_section({"sub_total": []}) == {}


# Fixtures below are adapted from real naver-clova-ix/cord-v2 train examples
# (indices 134, 4, 35, 56), with irrelevant OCR/bounding-box metadata stripped.

MULTI_ITEM = {
    "menu": [
        {"nm": "Viet Milk Coffee", "cnt": "1", "price": "29.000"},
        {"nm": "Viet Milk Coffee", "cnt": "1", "price": "25.000"},
    ],
    "sub_total": {"subtotal_price": "54.000"},
    "total": {"total_price": "54.000", "cashprice": "56.000", "changeprice": "2.000"},
}

SINGLE_ITEM = {
    "menu": {"nm": "BASO BIHUN", "unitprice": "43.636", "cnt": "1", "price": "43.636"},
    "sub_total": {"subtotal_price": "43.636", "tax_price": "4.364"},
    "total": {"total_price": "48.000", "cashprice": "50.000", "changeprice": "2.000"},
}

MISSING_TOTAL = {
    "menu": {
        "nm": "Cuka Apel Moringa",
        "unitprice": "289000",
        "cnt": "1",
        "price": "289000",
    },
    "sub_total": {"subtotal_price": "289000"},
    "total": {"cashprice": "300000", "changeprice": "11000"},
}

DUPLICATE_SUBTOTAL = {
    "menu": [
        {"nm": "BASO TAHU", "unitprice": "43.636", "cnt": "1", "price": "43.636"},
        {"nm": "NASI PUTIH", "unitprice": "6.000", "cnt": "1", "price": "6.000"},
    ],
    "sub_total": {"subtotal_price": ["49.636", "49.636"], "tax_price": "4.964"},
    "total": {"total_price": "54.600", "cashprice": "60.100", "changeprice": "5.500"},
}


def test_convert_multi_item_receipt():
    invoice = convert_example(MULTI_ITEM)

    assert invoice.document_type == "receipt"
    assert invoice.currency == "IDR"
    assert invoice.grand_total == Decimal("54000")
    assert invoice.subtotal == Decimal("54000")
    assert invoice.tax is None
    assert len(invoice.line_items) == 2
    assert invoice.line_items[0].description == "Viet Milk Coffee"
    assert invoice.line_items[0].line_total == Decimal("29000")
    assert invoice.line_items[0].unit_price is None


def test_convert_single_item_receipt_unwraps_dict_menu():
    invoice = convert_example(SINGLE_ITEM)

    assert invoice.grand_total == Decimal("48000")
    assert invoice.subtotal == Decimal("43636")
    assert invoice.tax == Decimal("4364")
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].unit_price == Decimal("43636")


def test_convert_missing_total_is_rejected():
    with pytest.raises(ValidationError):
        convert_example(MISSING_TOTAL)


def test_convert_duplicate_subtotal_list_is_not_doubled():
    invoice = convert_example(DUPLICATE_SUBTOTAL)

    assert invoice.subtotal == Decimal("49636")
    assert invoice.grand_total == Decimal("54600")
    assert invoice.tax == Decimal("4964")
