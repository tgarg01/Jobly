"""Job Board — browse, filter, and manage jobs."""

import streamlit as st
import pandas as pd
from datetime import date
from utils.db import load_jobs, mark_applied, update_job, hide_job
from utils.constants import FLAG_KEYWORDS

st.set_page_config(page_title="Job Board — Jobly", page_icon=":clipboard:", layout="wide")
st.title(":clipboard: Job Board")

df = load_jobs(active_only=True)

if df.empty:
    st.info("No active jobs. Add some via the **Add Job** page!")
    st.stop()

# ── Sidebar Filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")

# Job Type filter
job_types = ["All"] + sorted(df["job_type"].dropna().unique().tolist()) if "job_type" in df.columns else ["All"]
selected_type = st.sidebar.selectbox("Job Type", job_types)

# Applied status filter
applied_filter = st.sidebar.selectbox("Applied Status", ["All", "Applied", "Not Applied"])

# Company filter
companies = ["All"] + sorted(df["company"].dropna().unique().tolist()) if "company" in df.columns else ["All"]
selected_company = st.sidebar.selectbox("Company", companies)

# Keyword search
keyword = st.sidebar.text_input("Keyword Search", placeholder="e.g. CRISPR, oncology...")

# ── Apply Filters ──────────────────────────────────────────────────────────────
filtered = df.copy()

if selected_type != "All" and "job_type" in filtered.columns:
    filtered = filtered[filtered["job_type"] == selected_type]

if applied_filter == "Applied":
    filtered = filtered[filtered["applied_date"].notna() & (filtered["applied_date"] != "")]
elif applied_filter == "Not Applied":
    filtered = filtered[filtered["applied_date"].isna() | (filtered["applied_date"] == "")]

if selected_company != "All" and "company" in filtered.columns:
    filtered = filtered[filtered["company"] == selected_company]

if keyword.strip():
    kw = keyword.strip().lower()
    text_cols = ["company", "job_title", "key_skills", "comments", "location"]
    mask = pd.Series(False, index=filtered.index)
    for col in text_cols:
        if col in filtered.columns:
            mask = mask | filtered[col].fillna("").str.lower().str.contains(kw, na=False)
    filtered = filtered[mask]

st.caption(f"Showing {len(filtered)} of {len(df)} active jobs")

# ── Display Jobs ───────────────────────────────────────────────────────────────
if filtered.empty:
    st.warning("No jobs match your filters.")
    st.stop()

for idx, row in filtered.iterrows():
    job_id = int(row["id"])
    company = row.get("company", "—")
    title = row.get("job_title", "—")
    location = row.get("location", "—")
    job_type = row.get("job_type", "—")
    fit_score = row.get("fit_score", None)
    applied_date = row.get("applied_date", None)
    salary = row.get("salary", None)
    comments = row.get("comments", None)
    job_link = row.get("job_link", None)
    key_skills = row.get("key_skills", None)

    # Color coding
    comment_lower = str(comments or "").lower()
    is_flagged = any(kw in comment_lower for kw in FLAG_KEYWORDS)

    if is_flagged:
        indicator = ":red_circle:"
    elif applied_date and str(applied_date).strip():
        indicator = ":green_circle:"
    else:
        indicator = ":white_circle:"

    with st.expander(f"{indicator} **{company}** — {title}  |  {location}  |  {job_type}", expanded=False):
        info_col, action_col = st.columns([3, 1])

        with info_col:
            st.markdown(f"**Fit Score:** {fit_score if fit_score is not None else '—'}")
            st.markdown(f"**Salary:** {salary if salary else '—'}")
            st.markdown(f"**Skills:** {key_skills if key_skills else '—'}")
            st.markdown(f"**Applied:** {applied_date if applied_date else 'Not yet'}")
            st.markdown(f"**Comments:** {comments if comments else '—'}")

        with action_col:
            # Mark Applied
            if not applied_date or not str(applied_date).strip():
                if st.button("Mark Applied", key=f"apply_{job_id}"):
                    mark_applied(job_id)
                    st.rerun()

            # Add / Edit Comment
            new_comment = st.text_input(
                "Comment",
                value=comments if comments else "",
                key=f"comment_{job_id}",
                label_visibility="collapsed",
                placeholder="Add a comment...",
            )
            if st.button("Save Comment", key=f"save_comment_{job_id}"):
                update_job(job_id, {"comments": new_comment})
                st.rerun()

            # Open Job Link
            if job_link and str(job_link).strip():
                st.link_button("Open Job Link", str(job_link), use_container_width=True)

            # Hide Job
            if st.button("Hide Job", key=f"hide_{job_id}"):
                hide_job(job_id)
                st.rerun()
