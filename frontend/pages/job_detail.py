import os

import pandas as pd
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8001")

st.set_page_config(page_title="Job Detail", layout="wide")

job_id = st.query_params.get("job_id")
if job_id is None:
    st.error("No job_id given — open this page via a link from the main app.")
    st.stop()

job_id = int(job_id)
st.title(f"Job {job_id}")

response = requests.get(f"{API_BASE}/ledger/full")
if not response.ok:
    st.error(f"Could not load ledger: {response.status_code}")
    st.stop()

items = response.json()
item = next((i for i in items if i["job_id"] == job_id), None)
if item is None:
    st.warning("This job isn't in the ledger (it may still be pending).")
    st.stop()

st.write(f"**Status:** {item['status']}")
if item.get("error"):
    st.write(f"**Error:** {item['error']}")
if item.get("ledger_entry_error"):
    st.write(f"**Ledger decode error:** {item['ledger_entry_error']}")

entry = item.get("ledger_entry")
if not entry:
    st.info("No ledger entry — nothing was extracted for this job.")
    st.stop()

st.write(f"**Needs review:** {entry.get('needs_review')}")
if entry.get("review_reason"):
    st.write(f"**Review reason:** {entry.get('review_reason')}")

invoice_data = dict(entry.get("invoice_data") or {})
line_items = invoice_data.pop("line_items", [])

st.subheader("Fields")
fields_df = pd.DataFrame(
    {"field": list(invoice_data.keys()), "value": list(invoice_data.values())}
)
st.dataframe(fields_df, use_container_width=True, hide_index=True)

st.subheader("Line items")
if line_items:
    st.dataframe(pd.DataFrame(line_items), use_container_width=True, hide_index=True)
else:
    st.info("No line items.")
