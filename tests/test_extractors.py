from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import openai
import pytest

from invoice_pipeline.workflow import extractors
from invoice_pipeline.workflow.extractors import (
    FrontierExtractor,
    SpecialistExtractor,
    _parse_wire_invoice,
)
from invoice_pipeline.schema import Invoice, LineItem, WireInvoice


def _invoice(**overrides) -> Invoice:
    defaults = dict(
        document_type="receipt",
        currency="USD",
        invoice_number="INV-1",
        grand_total=Decimal("100"),
        subtotal=Decimal("100"),
        line_items=[
            LineItem(
                description="Item",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            ),
        ],
    )
    defaults.update(overrides)
    return Invoice(**defaults)


def _fake_specialist_client(content: str) -> MagicMock:
    message = MagicMock(content=content)
    choice = MagicMock(message=message)
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[choice])
    )
    return fake_client


def _fake_specialist_client_raising(exc: Exception) -> MagicMock:
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=exc)
    return fake_client


def _fake_frontier_client(
    invoice: Invoice | None = None, raises: bool = False
) -> MagicMock:
    structured = MagicMock()
    if raises:
        structured.ainvoke = AsyncMock(side_effect=RuntimeError("frontier boom"))
    else:
        # with_structured_output(..., include_raw=True) returns this dict shape,
        # not the parsed model directly.
        structured.ainvoke = AsyncMock(
            return_value={
                "raw": MagicMock(),
                "parsed": invoice,
                "parsing_error": None,
            }
        )
    fake_client = MagicMock()
    fake_client.with_structured_output.return_value = structured
    return fake_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_image_io(monkeypatch):
    monkeypatch.setattr(
        extractors, "load_image_b64", lambda path: ("fakeb64", "image/png")
    )


def _specialist(client: MagicMock, seed: int | None = None) -> SpecialistExtractor:
    extractor = SpecialistExtractor(
        "http://vllm.test/v1", "key", "test-model", seed=seed
    )
    extractor._client = client
    return extractor


def _frontier(client: MagicMock) -> FrontierExtractor:
    extractor = FrontierExtractor("test-model")
    extractor._client = client
    return extractor


@pytest.mark.anyio
async def test_specialist_parses_valid_json_into_invoice():
    invoice = _invoice()
    extractor = _specialist(_fake_specialist_client(invoice.model_dump_json()))

    result = await extractor.extract_invoice("fake.png")

    assert result.parse_error is None
    assert result.invoice == invoice


@pytest.mark.anyio
async def test_specialist_reports_parse_error_on_invalid_json():
    extractor = _specialist(_fake_specialist_client("not valid json"))

    result = await extractor.extract_invoice("fake.png")

    assert result.invoice is None
    assert result.parse_error.startswith("invalid_output:")


@pytest.mark.anyio
async def test_specialist_reraises_connectivity_errors_for_arq_retry():
    exc = openai.APIConnectionError(request=httpx.Request("POST", "http://vllm.test"))
    extractor = _specialist(_fake_specialist_client_raising(exc))

    with pytest.raises(openai.APIConnectionError):
        await extractor.extract_invoice("fake.png")


@pytest.mark.anyio
async def test_specialist_sends_wire_schema_via_response_format():
    invoice = _invoice()
    client = _fake_specialist_client(invoice.model_dump_json())
    extractor = _specialist(client)

    await extractor.extract_invoice("fake.png")

    kwargs = client.chat.completions.create.await_args.kwargs
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "WireInvoice",
            "schema": WireInvoice.model_json_schema(),
            "strict": True,
        },
    }
    assert "extra_body" not in kwargs


@pytest.mark.anyio
async def test_specialist_parses_locale_formatted_wire_amounts():
    raw = """{
        "document_type": "invoice", "currency": "USD",
        "grand_total": "20.000,00", "subtotal": "20.000,00",
        "line_items": []
    }"""
    extractor = _specialist(_fake_specialist_client(raw))

    result = await extractor.extract_invoice("fake.png")

    assert result.parse_error is None
    assert result.invoice.grand_total == Decimal("20000.00")


@pytest.mark.anyio
async def test_specialist_parses_negative_grand_total_from_wire_response():
    raw = """{
        "document_type": "invoice", "currency": "USD",
        "grand_total": "-1500.00", "line_items": []
    }"""
    extractor = _specialist(_fake_specialist_client(raw))

    result = await extractor.extract_invoice("fake.png")

    assert result.parse_error is None
    assert result.invoice.grand_total == Decimal("-1500.00")


@pytest.mark.anyio
async def test_specialist_strips_sign_from_wire_discount():
    raw = """{
        "document_type": "invoice", "currency": "USD",
        "grand_total": "100.00", "discount": "-25.00", "line_items": []
    }"""
    extractor = _specialist(_fake_specialist_client(raw))

    result = await extractor.extract_invoice("fake.png")

    assert result.parse_error is None
    assert result.invoice.discount == Decimal("25.00")


def test_parse_wire_invoice_converts_top_level_money_fields():
    data = {
        "grand_total": "1.500,50",
        "subtotal": "1.000,00",
        "tax": "500,50",
        "service_charge": None,
        "discount": None,
        "line_items": [],
    }

    result = _parse_wire_invoice(data)

    assert result["grand_total"] == Decimal("1500.50")
    assert result["subtotal"] == Decimal("1000.00")
    assert result["tax"] == Decimal("500.50")
    assert result["service_charge"] is None
    assert result["discount"] is None


def test_parse_wire_invoice_strips_sign_from_discount_only():
    data = {
        "grand_total": "-100.00",
        "discount": "-10.00",
        "line_items": [],
    }

    result = _parse_wire_invoice(data)

    assert result["grand_total"] == Decimal("-100.00")
    assert result["discount"] == Decimal("10.00")


def test_parse_wire_invoice_converts_line_item_money_fields():
    data = {
        "grand_total": "100.00",
        "discount": None,
        "line_items": [
            {
                "description": "Widget",
                "unit_price": "20,00",
                "quantity": "2",
                "line_total": "40,00",
            }
        ],
    }

    result = _parse_wire_invoice(data)

    item = result["line_items"][0]
    assert item["unit_price"] == Decimal("20.00")
    assert item["quantity"] == Decimal("2")
    assert item["line_total"] == Decimal("40.00")


@pytest.mark.anyio
async def test_specialist_sends_configured_model_name():
    invoice = _invoice()
    client = _fake_specialist_client(invoice.model_dump_json())
    extractor = _specialist(client)

    await extractor.extract_invoice("fake.png")

    assert client.chat.completions.create.await_args.kwargs["model"] == "test-model"


@pytest.mark.anyio
async def test_specialist_sends_configured_seed():
    invoice = _invoice()
    client = _fake_specialist_client(invoice.model_dump_json())
    extractor = _specialist(client, seed=42)

    await extractor.extract_invoice("fake.png")

    assert client.chat.completions.create.await_args.kwargs["seed"] == 42


@pytest.mark.anyio
async def test_specialist_defaults_to_no_seed():
    invoice = _invoice()
    client = _fake_specialist_client(invoice.model_dump_json())
    extractor = _specialist(client)

    await extractor.extract_invoice("fake.png")

    assert client.chat.completions.create.await_args.kwargs["seed"] is None


@pytest.mark.anyio
async def test_frontier_returns_structured_invoice():
    invoice = _invoice()
    extractor = _frontier(_fake_frontier_client(invoice))

    result = await extractor.extract_invoice("fake.png")

    assert result.parse_error is None
    assert result.invoice == invoice


@pytest.mark.anyio
async def test_frontier_reports_parse_error_when_call_raises():
    extractor = _frontier(_fake_frontier_client(raises=True))

    result = await extractor.extract_invoice("fake.png")

    assert result.invoice is None
    assert result.parse_error.startswith("unknown:")


@pytest.mark.anyio
async def test_frontier_reraises_connectivity_errors_for_arq_retry():
    exc = anthropic.APIConnectionError(
        request=httpx.Request("POST", "http://anthropic.test")
    )
    structured = MagicMock()
    structured.ainvoke = AsyncMock(side_effect=exc)
    fake_client = MagicMock()
    fake_client.with_structured_output.return_value = structured
    extractor = _frontier(fake_client)

    with pytest.raises(anthropic.APIConnectionError):
        await extractor.extract_invoice("fake.png")


@pytest.mark.anyio
async def test_frontier_appends_extra_context_to_prompt():
    invoice = _invoice()
    client = _fake_frontier_client(invoice)
    extractor = _frontier(client)

    await extractor.extract_invoice("fake.png", "issues: grand total mismatch")

    sent = client.with_structured_output.return_value.ainvoke.await_args.args[0][0]
    prompt = sent["content"][0]["text"]
    assert "issues: grand total mismatch" in prompt
