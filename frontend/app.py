import os

import pandas as pd
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8001")

st.set_page_config(page_title="Invoice Agent", layout="wide")
st.title("Invoice Agent")

upload_tab, review_tab, ledger_tab = st.tabs(["Upload", "Review Queue", "Full Ledger"])


def summary_row(item, link_page):
    return {
        "job_id": item["job_id"],
        "status": item["status"],
        "created_at": pd.to_datetime(item.get("created_at")),
        "link": f"/{link_page}?job_id={item['job_id']}",
    }


def render_entries(items, link_page, link_label):
    if not items:
        st.info("Nothing to show.")
        return

    summary_df = pd.DataFrame(summary_row(item, link_page) for item in items)
    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "job_id": st.column_config.Column("Job ID"),
            "status": st.column_config.Column("Status"),
            "created_at": st.column_config.DatetimeColumn(
                "Created", format="D/M/YYYY h:mm A"
            ),
            "link": st.column_config.LinkColumn("Details", display_text=link_label),
        },
    )


with upload_tab:
    st.subheader("Upload an invoice or receipt")
    uploaded_file = st.file_uploader("Choose an image", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None and st.button("Submit for processing"):
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
        }
        response = requests.post(f"{API_BASE}/extraction/upload_image", files=files)
        if response.ok:
            data = response.json()
            st.session_state["job_id"] = data["job_id"]
            st.success(f"Uploaded — job id {data['job_id']}")
        else:
            st.error(f"Upload failed: {response.status_code} — {response.text}")

    if "job_id" in st.session_state:
        job_id = st.session_state["job_id"]

        @st.fragment(run_every=2)
        def poll_status(job_id=job_id):
            response = requests.get(f"{API_BASE}/extraction/status/{job_id}")
            if not response.ok:
                st.error(f"Status check failed: {response.status_code}")
                return
            job = response.json()["job"]
            status = job["status"]

            st.write(f"**Job {job_id}** — status: `{status}`")
            if status == "pending":
                st.info("Still processing...")
            elif status == "complete":
                st.success("Extraction complete — check the Review Queue tab.")
            elif status == "needs_review":
                st.warning(f"Needs review: {job['error']}")
            elif status == "error":
                st.error(f"Job failed: {job['error']}")

        poll_status()

with review_tab:
    st.subheader("Items needing review")
    if st.button("Refresh", key="refresh_review"):
        st.rerun()

    response = requests.get(f"{API_BASE}/ledger/review")
    if not response.ok:
        st.error(f"Could not load review queue: {response.status_code}")
    else:
        render_entries(response.json(), link_page="job_edit", link_label="Edit")

with ledger_tab:
    st.subheader("Full ledger")
    if st.button("Refresh", key="refresh_ledger"):
        st.rerun()

    response = requests.get(f"{API_BASE}/ledger/full")
    if not response.ok:
        st.error(f"Could not load ledger: {response.status_code}")
    else:
        render_entries(response.json(), link_page="job_detail", link_label="View")
