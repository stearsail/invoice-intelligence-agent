"""Streamlit UI for reviewing golden-set candidates.

Separate from the actual app entirely — no shared routers, no shared pages,
its own process. Replaces the manual accept()/reject() loop in
explore/golden_review.ipynb with a page instead of re-running notebook
cells; same three files (unverified/test/rejected.jsonl), same rules.

Run with: uv run streamlit run scripts/golden_review_app.py
"""

import json
from datetime import date
from decimal import InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from invoice_pipeline.schema import Invoice

LINE_ITEM_COLUMNS = ["description", "quantity", "unit_price", "line_total"]

REPO_ROOT = Path(__file__).parent.parent
GOLDEN_DIR = REPO_ROOT / "data" / "golden"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

UNVERIFIED_PATH = GOLDEN_DIR / "unverified.jsonl"
VERIFIED_PATH = GOLDEN_DIR / "test.jsonl"
REJECTED_PATH = GOLDEN_DIR / "rejected.jsonl"


# --- File I/O — plain functions, no Streamlit dependency, unit-testable ---


def record_key(record: dict) -> str:
    return f"{record['source']}:{record['index']}"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def reviewed_keys(golden_dir: Path) -> set[str]:
    verified = load_jsonl(golden_dir / "test.jsonl")
    rejected = load_jsonl(golden_dir / "rejected.jsonl")
    return {record_key(r) for r in verified} | {record_key(r) for r in rejected}


def next_candidate(records: list[dict], reviewed: set[str]) -> dict | None:
    for record in records:
        if record_key(record) not in reviewed:
            return record
    return None


def accept(golden_dir: Path, record: dict, edited_invoice: dict) -> None:
    append_jsonl(golden_dir / "test.jsonl", {**record, "invoice": edited_invoice})


def reject(golden_dir: Path, record: dict, reason: str) -> None:
    append_jsonl(golden_dir / "rejected.jsonl", {**record, "_reject_reason": reason})


# --- Streamlit UI ----------------------------------------------------------


def _text_or_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def _party_form(label: str, party: dict | None, key_prefix: str) -> dict | None:
    party = party or {}
    st.markdown(f"**{label}**")
    row1 = st.columns(2)
    with row1[0]:
        name = st.text_input(
            "Name", value=party.get("name") or "", key=f"{key_prefix}-name"
        )
    with row1[1]:
        tax_id = st.text_input(
            "Tax ID", value=party.get("tax_id") or "", key=f"{key_prefix}-tax_id"
        )
    row2 = st.columns(2)
    with row2[0]:
        address = st.text_input(
            "Address", value=party.get("address") or "", key=f"{key_prefix}-address"
        )
    with row2[1]:
        iban = st.text_input(
            "IBAN", value=party.get("iban") or "", key=f"{key_prefix}-iban"
        )
    if not name.strip():
        return None
    return {
        "name": name.strip(),
        "address": _text_or_none(address),
        "tax_id": _text_or_none(tax_id),
        "iban": _text_or_none(iban),
    }


def _date_input(label: str, value: str | None, key: str) -> str | None:
    parsed = date.fromisoformat(value) if value else None
    result = st.date_input(label, value=parsed, key=key)
    return result.isoformat() if isinstance(result, date) else None


def _invoice_form(invoice: dict, key_prefix: str) -> dict:
    """Renders editable widgets for one invoice and returns the edited dict
    (not yet validated — that happens once, against the real schema, right
    before accept)."""
    row1 = st.columns(2)
    with row1[0]:
        document_type = st.selectbox(
            "Document type",
            ["invoice", "receipt"],
            index=["invoice", "receipt"].index(invoice.get("document_type", "receipt")),
            key=f"{key_prefix}-doctype",
        )
    with row1[1]:
        invoice_number = st.text_input(
            "Invoice number",
            value=invoice.get("invoice_number") or "",
            key=f"{key_prefix}-num",
        )

    row2 = st.columns(2)
    with row2[0]:
        currency = st.text_input(
            "Currency",
            value=invoice.get("currency") or "",
            key=f"{key_prefix}-currency",
        )
    with row2[1]:
        issue_date = _date_input(
            "Issue date", invoice.get("issue_date"), key=f"{key_prefix}-issue"
        )

    due_date = _date_input("Due date", invoice.get("due_date"), key=f"{key_prefix}-due")

    vendor = _party_form("Vendor", invoice.get("vendor"), f"{key_prefix}-vendor")
    customer = (
        _party_form("Customer", invoice.get("customer"), f"{key_prefix}-customer")
        if document_type == "invoice"
        else None
    )

    st.markdown("**Line items**")
    # a bare [] loses its column names/types entirely once data_editor can't
    # infer them from any rows — an explicit-columns DataFrame keeps the
    # header (and the add-row affordance) even when there are zero rows yet.
    line_items_df = pd.DataFrame(
        invoice.get("line_items") or [], columns=LINE_ITEM_COLUMNS
    )
    edited_lines = st.data_editor(
        line_items_df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{key_prefix}-lines",
    )
    line_items = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in edited_lines.to_dict(orient="records")
    ]
    # drop the untouched trailing template row data_editor always shows
    line_items = [
        row for row in line_items if any(v not in (None, "") for v in row.values())
    ]

    money_row1 = st.columns(2)
    with money_row1[0]:
        subtotal = st.text_input(
            "Subtotal",
            value=_money_str(invoice.get("subtotal")),
            key=f"{key_prefix}-subtotal",
        )
    with money_row1[1]:
        tax = st.text_input(
            "Tax", value=_money_str(invoice.get("tax")), key=f"{key_prefix}-tax"
        )

    money_row2 = st.columns(2)
    with money_row2[0]:
        service_charge = st.text_input(
            "Service charge",
            value=_money_str(invoice.get("service_charge")),
            key=f"{key_prefix}-service",
        )
    with money_row2[1]:
        discount = st.text_input(
            "Discount",
            value=_money_str(invoice.get("discount")),
            key=f"{key_prefix}-discount",
        )
    grand_total = st.text_input(
        "Grand total",
        value=_money_str(invoice.get("grand_total")),
        key=f"{key_prefix}-grand",
    )

    return {
        "document_type": document_type,
        "invoice_number": _text_or_none(invoice_number),
        "currency": currency.strip().upper(),
        "issue_date": issue_date,
        "due_date": due_date,
        "vendor": vendor,
        "customer": customer,
        "line_items": line_items,
        "subtotal": _text_or_none(subtotal),
        "tax": _text_or_none(tax),
        "service_charge": _text_or_none(service_charge),
        "discount": _text_or_none(discount),
        "grand_total": grand_total.strip(),
        "confidence_notes": invoice.get("confidence_notes") or [],
    }


def _money_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def main() -> None:
    st.set_page_config(page_title="Golden Set Review", layout="wide")

    records = load_jsonl(UNVERIFIED_PATH)
    reviewed = reviewed_keys(GOLDEN_DIR)
    done = sum(1 for r in records if record_key(r) in reviewed)

    st.title("Golden Set Review")
    st.caption(f"{done} / {len(records)} reviewed")

    record = next_candidate(records, reviewed)
    if record is None:
        st.success("Nothing left to review.")
        return

    key_prefix = record_key(record)
    image_col, form_col = st.columns([1, 1])

    with image_col:
        image_path = PROCESSED_DIR / record["image_path"]
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.warning(f"Image file not found: {image_path}")

    with form_col:
        st.caption(f"{record['source']} · index {record['index']}")
        edited = _invoice_form(record["invoice"], key_prefix)

        accept_col, reject_col = st.columns(2)
        with accept_col:
            if st.button("Accept", type="primary", use_container_width=True):
                try:
                    Invoice.model_validate(edited)
                except (ValidationError, InvalidOperation) as e:
                    st.error(f"Still invalid — fix before accepting:\n\n{e}")
                else:
                    accept(GOLDEN_DIR, record, edited)
                    st.rerun()

        with reject_col:
            with st.popover("Reject", use_container_width=True):
                reason = st.text_input("Reason", key=f"{key_prefix}-reason")
                if st.button("Confirm reject", disabled=not reason.strip()):
                    reject(GOLDEN_DIR, record, reason.strip())
                    st.rerun()


if __name__ == "__main__":
    main()
