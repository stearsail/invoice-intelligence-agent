import json
from pathlib import Path
from invoice_agent.converters.cord import convert_example
from datasets import load_dataset, Dataset
from pydantic import ValidationError

output_dir = Path(__file__).parent.parent / "data" / "processed"
output_dir.mkdir(parents=True, exist_ok=True)

train_set = load_dataset("naver-clova-ix/cord-v2", split="train")
test_set = load_dataset("naver-clova-ix/cord-v2", split="test")


def build_dataset(output_file: str, dataset: Dataset, split: str = "train") -> None:
    records, skipped = [], []
    for i, example in enumerate(dataset):
        loaded = json.loads(example["ground_truth"])
        annotation = loaded["gt_parse"]
        try:
            invoice = convert_example(annotation)
        except ValidationError as e:
            skipped.append({"index": i, "reason": str(e)})
            continue
        record = {
            "source": "cord",
            "split": split,
            "index": i,
            "invoice": invoice.model_dump(mode="json"),
        }
        records.append(record)

    with open(output_dir / f"{output_file}_{split}.jsonl", "w", encoding="utf-8") as f:
        for line in records:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    with open(
        output_dir / f"{output_file}_{split}_skipped.jsonl", "w", encoding="utf-8"
    ) as f:
        for line in skipped:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print(f"Succesfully added {len(records)} lines to JSONL \nFailed {len(skipped)}")


build_dataset("cord", train_set, "train")
build_dataset("cord", test_set, "test")
