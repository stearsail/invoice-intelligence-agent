import json
import random
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
GOLDEN_DIR = Path(__file__).parent.parent / "data" / "golden"

GOLDEN_FRACTION = 0.0275
VAL_FRACTION = 0.10
SEED = 42


def _load_source_records(source_dir: Path) -> list[dict]:
    records = []
    for jsonl_path in sorted(source_dir.glob("*.jsonl")):
        if jsonl_path.name.endswith("_skipped.jsonl"):
            continue
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                # image_path is relative to the source's own directory
                # (e.g. data/processed/CORD/); rewrite it relative to the
                # pooled directory (data/processed/) instead.
                record["image_path"] = f"{source_dir.name}/{record['image_path']}"
                records.append(record)
    return records


def _load_reviewed_image_paths() -> set[str]:
    """image_paths already human-reviewed — accepted into the golden set or
    rejected as unusable. These must never re-enter train/val, and never be
    re-drawn as a fresh golden candidate either: without this exclusion,
    re-running this script after the source mix changes (e.g. swapping one
    dataset for another) reshuffles everything from scratch and can silently
    hand an already-verified golden document back to training."""
    paths = set()
    for jsonl_path in (GOLDEN_DIR / "test.jsonl", GOLDEN_DIR / "rejected.jsonl"):
        if not jsonl_path.exists():
            continue
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                paths.add(json.loads(line)["image_path"])
    return paths


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_splits() -> None:
    random.seed(SEED)
    reviewed_paths = _load_reviewed_image_paths()
    train_records, val_records, golden_records = [], [], []

    source_dirs = [d for d in sorted(PROCESSED_DIR.iterdir()) if d.is_dir()]
    for source_dir in source_dirs:
        records = _load_source_records(source_dir)
        records = [r for r in records if r["image_path"] not in reviewed_paths]
        random.shuffle(records)

        n_golden = round(len(records) * GOLDEN_FRACTION)
        golden = records[:n_golden]
        remaining = records[n_golden:]

        n_val = round(len(remaining) * VAL_FRACTION)
        val = remaining[:n_val]
        train = remaining[n_val:]

        print(
            f"{source_dir.name}: {len(records)} available (excluding already-reviewed) -> "
            f"{len(train)} train / {len(val)} val / {len(golden)} new golden candidates"
        )

        train_records.extend(train)
        val_records.extend(val)
        golden_records.extend(golden)

    random.shuffle(train_records)
    random.shuffle(val_records)
    random.shuffle(golden_records)

    _write_jsonl(train_records, PROCESSED_DIR / "train.jsonl")
    _write_jsonl(val_records, PROCESSED_DIR / "val.jsonl")
    _write_jsonl(golden_records, GOLDEN_DIR / "unverified.jsonl")

    print(
        f"\nTotal: {len(train_records)} train / {len(val_records)} val / "
        f"{len(golden_records)} new golden candidates (pending manual review before use) "
        f"— {len(reviewed_paths)} already-reviewed documents excluded from all splits"
    )


if __name__ == "__main__":
    build_splits()
