import argparse
import base64
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from datasets import load_dataset
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from vllm import LLM, SamplingParams

class Party(BaseModel):
    # "ignore" drops contact fields the model reads (email/phone/website) that
    # aren't in the project schema; name optional so a missed name doesn't lose
    # the record — nameless parties are coerced to None in _normalize.
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    address: str | None = None
    tax_id: str | None = None
    iban: str | None = None


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str | None = None
    unit_price: Decimal | None = None
    quantity: Decimal | None = None
    line_total: Decimal | None = None


class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    vendor: Party | None = None
    customer: Party | None = None
    document_type: Literal["invoice", "receipt", "credit_note"]
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    line_items: list[LineItem] = Field(default_factory=list)
    grand_total: Decimal
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    service_charge: Decimal | None = None
    discount: Decimal | None = None
    confidence_notes: list[str] = Field(default_factory=list)


FATURA_REPO = "mathieu1256/FATURA2-invoices"
MODEL = "unsloth/Qwen3-VL-32B-Instruct"
PROMPT = (
    "Extract the invoice as JSON with exactly these keys: document_type "
    "('invoice'|'receipt'|'credit_note'), currency (3-letter ISO code, uppercase), "
    "grand_total, and optionally invoice_number, issue_date (YYYY-MM-DD), due_date, "
    "subtotal, tax, service_charge, discount; vendor and customer objects with "
    "{name, address, tax_id, iban}; line_items as a list of "
    "{description, unit_price, quantity, line_total}. "
    "Keep name and address SEPARATE — never merge the address into the name. "
    "Read currency and number formatting from the document. Use null for anything "
    "not present. Respond with ONLY the JSON object, no prose."
)


def _data_uri(image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end != -1 else text


def _normalize(invoice: "Invoice") -> "Invoice":
    if invoice.vendor is not None and invoice.vendor.name is None:
        invoice.vendor = None
    if invoice.customer is not None and invoice.customer.name is None:
        invoice.customer = None
    return invoice


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3000, help="images to label")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--output", default="./fatura_labeled")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--chunk", type=int, default=256)
    args = parser.parse_args()

    out_dir = Path(args.output)
    img_dir = out_dir / "images" / "train"
    img_dir.mkdir(parents=True, exist_ok=True)

    llm = LLM(
        model=args.model,
        dtype="bfloat16",
        gpu_memory_utilization=0.9,
        max_model_len=8192,
        limit_mm_per_prompt={"image": 1},
    )
    sampling_params = SamplingParams(temperature=0, max_tokens=args.max_tokens)

    ds = load_dataset(FATURA_REPO, split="train")
    ds = ds.shuffle(seed=42).select(range(min(args.n, len(ds))))
    print(f"Labeling {len(ds)} images (chunks of {args.chunk}) ...")

    n_records, n_skipped = 0, 0
    with (
        open(out_dir / "train.jsonl", "w", encoding="utf-8") as rec_f,
        open(out_dir / "train_skipped.jsonl", "w", encoding="utf-8") as skip_f,
    ):
        for start in range(0, len(ds), args.chunk):
            chunk = ds[start : start + args.chunk]  # dict of column lists
            images = [img.convert("RGB") for img in chunk["image"]]

            conversations = [
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": _data_uri(img)}},
                            {"type": "text", "text": PROMPT},
                        ],
                    }
                ]
                for img in images
            ]

            outputs = llm.chat(conversations, sampling_params)

            for offset, (image, output) in enumerate(zip(images, outputs)):
                index = start + offset
                raw = output.outputs[0].text
                try:
                    invoice = _normalize(
                        Invoice.model_validate_json(_extract_json(raw))
                    )
                except ValidationError as e:
                    skip_f.write(
                        json.dumps(
                            {"index": index, "error": str(e), "raw": raw},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    skip_f.flush()
                    n_skipped += 1
                    continue
                image.save(img_dir / f"{index}.png", format="PNG")
                rec_f.write(
                    json.dumps(
                        {
                            "source": "fatura",
                            "split": "train",
                            "index": index,
                            "invoice": invoice.model_dump(mode="json"),
                            "image_path": f"images/train/{index}.png",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                rec_f.flush()
                n_records += 1

            done = min(start + args.chunk, len(ds))
            print(f"  {done}/{len(ds)}  (labeled: {n_records}, skipped: {n_skipped})")

    print(f"\nLabeled {n_records}, skipped {n_skipped} of {len(ds)}")


if __name__ == "__main__":
    main()