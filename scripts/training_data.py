import json
from pathlib import Path
from PIL import Image
from torch.utils.data import Dataset

_INSTRUCTION = "Extract structured data from this receipt/invoice image as JSON."


class JsonlImageDataset(Dataset):
    """Lazily decodes one image per __getitem__ call instead of loading the
    entire dataset into memory upfront — building `[convert_to_conversation(r)
    for r in rows]` eagerly holds every decoded image in RAM simultaneously,
    which is what caused an OOM kill during training on the full pooled
    dataset (thousands of images at once vs. one batch's worth)."""

    def __init__(self, rows: list[dict], data_path: Path):
        self.rows = rows
        self.data_path = data_path

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict:
        return convert_to_conversation(self.rows[index], self.data_path)


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
