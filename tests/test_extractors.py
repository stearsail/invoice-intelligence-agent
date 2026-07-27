from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import openai
import pytest

from invoice_agent.agent import extractors
from invoice_agent.agent.extractors import FrontierExtractor, SpecialistExtractor
from invoice_agent.schema import Invoice, LineItem


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
        structured.ainvoke = AsyncMock(return_value=invoice)
    fake_client = MagicMock()
    fake_client.with_structured_output.return_value = structured
    return fake_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_image_io(monkeypatch):
    monkeypatch.setattr(extractors, "load_image_b64", lambda path: "fakeb64")


def _specialist(client: MagicMock) -> SpecialistExtractor:
    extractor = SpecialistExtractor("http://vllm.test/v1", "key", "test-model")
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
    assert result.parse_error.startswith("unknown:")


@pytest.mark.anyio
async def test_specialist_reraises_connectivity_errors_for_arq_retry():
    exc = openai.APIConnectionError(request=httpx.Request("POST", "http://vllm.test"))
    extractor = _specialist(_fake_specialist_client_raising(exc))

    with pytest.raises(openai.APIConnectionError):
        await extractor.extract_invoice("fake.png")


@pytest.mark.anyio
async def test_specialist_sends_configured_model_name():
    invoice = _invoice()
    client = _fake_specialist_client(invoice.model_dump_json())
    extractor = _specialist(client)

    await extractor.extract_invoice("fake.png")

    assert client.chat.completions.create.await_args.kwargs["model"] == "test-model"


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
