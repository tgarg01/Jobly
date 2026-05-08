"""Job Board — your tracker diary. List, filter, take notes, mark applied."""

import streamlit as st
import pandas as pd
from datetime import date
from utils.db import load_jobs, mark_applied, update_job, hide_job
from utils.constants import FLAG_KEYWORDS

st.set_page_config(page_title="Job Board — Jobly", page_icon=":clipboard:", layout="wide")
st.title(":clipboard: Job Tracker Diary")
st.caption("Your personal job tracker — every job you've found, in one list. "
           "Take notes, mark applied, and keep a running diary.")

# Sync logged-in user from URL on refresh, same as app.py.
if "user_email" not in st.session_state:
    qp_email = st.query_params.get("u")
    if qp_email and "@" in qp_email:
        st.session_state["user_email"] = qp_email.strip().lower()

if "user_email" not in st.session_state:
    st.warning("Please sign in on the home page first.")
    st.stop()

user_email = st.session_state["user_email"]
df = load_jobs(active_only=True, user_email=user_email)

if df.empty:
    st.info("No active jobs yet. Go to the home page, upload your resume, and search for jobs!")
    st.stop()

# ── Sidebar Filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")

job_types = ["All"]
if "job_type" in df.columns:
    job_types += sorted(df["job_type"].dropna().unique().tolist())
selected_type = st.sidebar.selectbox("Job Type", job_types)

applied_filter = st.sidebar.selectbox("Applied Status", ["All", "Applied", "Not Applied"])

companies = ["All"]
if "company" in df.columns:
    companies += sorted(df["company"].dropna().unique().tolist())
selected_company = st.sidebar.selectbox("Company", companies)

keyword = st.sidebar.text_input("Keyword Search", placeholder="e.g. CRISPR, oncology...")

sort_by = st.sidebar.selectbox(
    "Sort by",
    ["Newest First", "Fit Score", "Company A-Z", "Applied (recent first)"],
)

view_mode = st.sidebar.radio(
    "View",
    ["Compact list", "Detailed diary"],
    help="Compact list = scan many jobs at once. Detailed diary = full notes per job.",
)

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

if sort_by == "Fit Score" and "fit_score" in filtered.columns:
    filtered = filtered.sort_values("fit_score", ascending=False)
elif sort_by == "Company A-Z" and "company" in filtered.columns:
    filtered = filtered.sort_values("company", ascending=True)
elif sort_by == "Applied (recent first)" and "applied_date" in filtered.columns:
    filtered = filtered.sort_values("applied_date", ascending=False, na_position="last")
else:
    filtered = filtered.sort_values("id", ascending=False)

# ── Summary Bar ────────────────────────────────────────────────────────────────
total = len(df)
applied_count = int(df["applied_date"].notna().sum()) if "applied_date" in df.columns else 0
pending_count = total - applied_count

s1, s2, s3, s4 = st.columns(4)
s1.metric("Total Jobs", total)
s2.metric("Applied", applied_count)
s3.metric("Pending", pending_count)
s4.metric("Showing", len(filtered))

st.markdown("---")

csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Export as CSV",
    data=csv,
    file_name="jobly_export.csv",
    mime="text/csv",
)

if filtered.empty:
    st.warning("No jobs match your filters.")
    st.stop()

# ── Render Jobs ────────────────────────────────────────────────────────────────

def _status_marker(applied_date, comments) -> str:
    comment_lower = str(comments or "").lower()
    if any(kw in comment_lower for kw in FLAG_KEYWORDS):
        return ":red_circle:"
    if applied_date and str(applied_date).strip():
        return ":green_circle:"
    return ":white_circle:"


if view_mode == "Compact list":
    st.markdown(
        "**Legend:** :white_circle: not applied · :green_circle: applied · "
        ":red_circle: flagged (expired / irrelevant)"
    )
    st.markdown("")

    # Header row
    h = st.columns([0.4, 2.4, 3.4, 1.6, 0.8, 1.2, 1.2])
    h[0].markdown("**·**")
    h[1].markdown("**Company**")
    h[2].markdown("**Job Title**")
    h[3].markdown("**Location**")
    h[4].markdown("**Score**")
    h[5].markdown("**Applied**")
    h[6].markdown("**Actions**")
    st.divider()

    for _, row in filtered.iterrows():
        job_id = int(row["id"])
        company = row.get("company", "—") or "—"
        title = row.get("job_title", "—") or "—"
        location = row.get("location") or "—"
        fit_score = row.get("fit_score")
        applied_date = row.get("applied_date")
        job_link = row.get("job_link")
        comments = row.get("comments")

        c = st.columns([0.4, 2.4, 3.4, 1.6, 0.8, 1.2, 1.2])
        c[0].markdown(_status_marker(applied_date, comments))
        c[1].markdown(f"**{company}**")
        if job_link and str(job_link).strip():
            c[2].markdown(f"[{title}]({job_link})")
        else:
            c[2].markdown(title)
        c[3].markdown(location)
        c[4].markdown(str(fit_score) if fit_score is not None else "—")
        c[5].markdown(str(applied_date) if applied_date else "—")

        with c[6]:
            act_a, act_b = st.columns(2)
            with act_a:
                if not applied_date or not str(applied_date).strip():
                    if st.button("Applied", key=f"q_apply_{job_id}", use_container_width=True):
                        mark_applied(job_id)
                        st.rerun()
                else:
                    st.caption("✓")
            with act_b:
                if st.button("✕", key=f"q_hide_{job_id}", help="Remove from tracker",
                             use_container_width=True):
                    hide_job(job_id)
                    st.rerun()

        # Notes are still editable in compact view, just collapsed
        with st.expander("Notes", expanded=False):
            new_comment = st.text_area(
                "Notes",
                value=comments if comments else "",
                key=f"q_comment_{job_id}",
                label_visibility="collapsed",
                placeholder="Add notes (e.g. applied via email, recruiter call set, interview scheduled)...",
                height=80,
            )
            if st.button("Save Notes", key=f"q_save_{job_id}"):
                update_job(job_id, {"comments": new_comment})
                st.rerun()

else:
    # Detailed diary view
    for _, row in filtered.iterrows():
        job_id = int(row["id"])
        company = row.get("company", "—")
        title = row.get("job_title", "—")
        location = row.get("location", "—") or "—"
        job_type = row.get("job_type", "—") or "—"
        fit_score = row.get("fit_score")
        applied_date = row.get("applied_date")
        salary = row.get("salary")
        comments = row.get("comments")
        job_link = row.get("job_link")
        key_skills = row.get("key_skills")
        posted_date = row.get("posted_date")
        added_on = row.get("added_on")

        marker = _status_marker(applied_date, comments)
        score_text = f"Score: {fit_score}" if fit_score is not None else ""

        with st.expander(
            f"{marker} **{company}** — {title}  |  {location}  |  {job_type}  |  {score_text}",
            expanded=False,
        ):
            detail_col, action_col = st.columns([3, 1])

            with detail_col:
                st.markdown(f"**Job Title:** {title}")
                st.markdown(f"**Company:** {company}")
                st.markdown(f"**Location:** {location}")
                st.markdown(f"**Type:** {job_type}")
                st.markdown(f"**Fit Score:** {fit_score if fit_score is not None else '—'}")
                st.markdown(f"**Salary:** {salary if salary else '—'}")
                st.markdown(f"**Skills:** {key_skills if key_skills else '—'}")
                st.markdown(f"**Posted:** {posted_date if posted_date else '—'}")
                st.markdown(f"**Added:** {added_on if added_on else '—'}")
                st.markdown(f"**Applied:** {applied_date if applied_date else 'Not yet'}")

                if comments:
                    st.markdown(f"**Your Notes:** {comments}")

            with action_col:
                if not applied_date or not str(applied_date).strip():
                    if st.button("Mark Applied", key=f"apply_{job_id}", use_container_width=True):
                        mark_applied(job_id)
                        st.rerun()
                else:
                    st.success("Applied!")

                if job_link and str(job_link).strip():
                    st.link_button("Open Job Link", str(job_link), use_container_width=True)

                st.markdown("**Your Notes:**")
                new_comment = st.text_area(
                    "Notes",
                    value=comments if comments else "",
                    key=f"comment_{job_id}",
                    label_visibility="collapsed",
                    placeholder="Add notes... (e.g. applied via email, heard back, interview scheduled)",
                    height=100,
                )
                if st.button("Save Notes", key=f"save_{job_id}", use_container_width=True):
                    update_job(job_id, {"comments": new_comment})
                    st.rerun()

                st.markdown("---")

                if st.button("Remove from Tracker", key=f"hide_{job_id}", use_container_width=True):
                    hide_job(job_id)
                    st.rerun()
