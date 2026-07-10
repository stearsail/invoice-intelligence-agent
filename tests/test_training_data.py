import json
from pathlib import Path

from PIL import Image

from invoice_agent.training_data import convert_to_conversation, load_jsonl_data


def test_convert_to_conversation_builds_expected_structure(tmp_path: Path):
    image_path = tmp_path / "receipt.png"
    Image.new("RGB", (100, 100)).save(image_path, format="PNG")

    row = {
        "image_path": "receipt.png",
        "invoice": {
            "document_type": "receipt",
            "currency": "USD",
            "grand_total": "10.00",
        },
    }

    conversation = convert_to_conversation(row, tmp_path)
    messages = conversation["messages"]

    assert len(messages) == 2

    user_message = messages[0]
    assert user_message["role"] == "user"
    assert user_message["content"][0]["type"] == "text"
    assert user_message["content"][1]["type"] == "image"

    assistant_message = messages[1]
    assert assistant_message["role"] == "assistant"
    assistant_text = assistant_message["content"][0]["text"]
    assert json.loads(assistant_text) == row["invoice"]


def test_load_jsonl_data_parses_lines_and_skips_blanks(tmp_path: Path):
    jsonl_path = tmp_path / "data.jsonl"
    jsonl_path.write_text('{"a": 1}\n\n{"b": 2}\n   \n{"c": 3}\n')

    rows = load_jsonl_data(jsonl_path)

    assert rows == [{"a": 1}, {"b": 2}, {"c": 3}]
