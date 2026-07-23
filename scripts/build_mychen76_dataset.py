import json
from pathlib import Path
from scripts.converters.mychen76 import convert_example
from datasets import load_dataset, Dataset
from pydantic import ValidationError
from PIL import Image

output_dir = Path(__file__).parent.parent / "data" / "processed" / "mychen76"
output_dir.mkdir(parents=True, exist_ok=True)

image_output_dir = output_dir / "images"


def _save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="PNG")


def build_dataset(dataset: Dataset, split: str = "train") -> None:
    records, skipped = [], []
    for i, example in enumerate(dataset):
        img_path = image_output_dir / split / f"{i}.png"
        try:
            invoice = convert_example(example["parsed_data"])
        except ValidationError as e:
            skipped.append({"index": i, "reason": str(e)})
            continue
        record = {
            "source": "mychen76",
            "split": split,
            "index": i,
            "invoice": invoice.model_dump(mode="json"),
            "image_path": str(img_path.relative_to(output_dir)),
        }
        records.append(record)
        _save_image(example["image"], img_path)

    with open(output_dir / f"{split}.jsonl", "w", encoding="utf-8") as f:
        for line in records:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    with open(output_dir / f"{split}_skipped.jsonl", "w", encoding="utf-8") as f:
        for line in skipped:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print(f"Succesfully added {len(records)} lines to JSONL \nFailed {len(skipped)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build the mychen76 invoices-and-receipts dataset from Hugging Face"
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "test", "valid"],
        default="train",
        help="Which split to convert",
    )
    args = parser.parse_args()

    dataset = load_dataset("mychen76/invoices-and-receipts_ocr_v1", split=args.split)
    build_dataset(dataset, args.split)
