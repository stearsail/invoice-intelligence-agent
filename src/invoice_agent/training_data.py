import json
from pathlib import Path
from PIL import Image

_INSTRUCTION = "This is the image of a business document. Invoice / receipt / credit note — extract the information from within it."


def convert_to_conversation(row: dict, data_path: Path) -> dict:
    img = Image.open(data_path / row["image_path"])
    img.load()

    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _INSTRUCTION},
                {"type": "image", "image": img},
            ],
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": json.dumps(row["invoice"])}],
        },
    ]
    return {"messages": conversation}


def load_jsonl_data(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    return lines
