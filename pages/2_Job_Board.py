"""Job Board — your tracker diary. List, filter, take notes, track outcomes."""

import streamlit as st
import pandas as pd
from utils.db import (
    load_jobs, mark_applied, set_job_status, update_job, hide_job, list_configs,
    delete_jobs_by_ids,
)
from utils.constants import FLAG_KEYWORDS
from utils.job_search import _is_allowed_url

st.set_page_config(page_title="Job Board — Jobly", page_icon=":clipboard:", layout="wide")
st.title(":clipboard: Job Tracker Diary")
st.caption("Your personal job tracker — every job you've found, in one list. "
           "Mark applied, then update to pass or fail when you hear back.")

# Sync logged-in user from URL on refresh.
if "user_email" not in st.session_state:
    qp_email = st.query_params.get("u")
    if qp_email and "@" in qp_email:
        st.session_state["user_email"] = qp_email.strip().lower()

if "user_email" not in st.session_state:
    st.warning("Please sign in on the home page first.")
    st.stop()

user_email = st.session_state["user_email"]

# ── Configuration filter ──────────────────────────────────────────────────────
configs = list_configs(user_email)
config_options: list[tuple[str, int | None]] = (
    [("All configurations", None)] + [(c["name"], c["id"]) for c in configs]
)
labels = [opt[0] for opt in config_options]

# Default to the active config from the home page if any.
default_idx = 0
active_id = st.session_state.get("active_config_id")
if active_id is not None:
    for i, (_, cid) in enumerate(config_options):
        if cid == active_id:
            default_idx = i
            break

st.sidebar.header("Configuration")
selected_label = st.sidebar.selectbox(
    "Show jobs from",
    labels,
    index=default_idx,
    key="board_config_picker",
)
selected_config_id = next(cid for label, cid in config_options if label == selected_label)
config_label_for_caption = selected_label

df = load_jobs(active_only=True, user_email=user_email, config_id=selected_config_id)

# ── Live filter by the active config's current radius / location ──────────────
# Each job stores the search_radius_miles and search_location it was found at.
# When the user shrinks the radius or changes the location on the home page,
# out-of-scope jobs vanish from the board (still in the DB; bumping the radius
# back up brings them back). Legacy rows with NULL fields are always shown.
if selected_config_id is not None and not df.empty:
    active_cfg = next((c for c in configs if c["id"] == selected_config_id), None)
    if active_cfg:
        cur_radius = active_cfg.get("radius_miles")
        cur_loc = active_cfg.get("location")
        if cur_radius is not None and "search_radius_miles" in df.columns:
            df = df[df["search_radius_miles"].fillna(0).astype(int) <= int(cur_radius)]
        if cur_loc and "search_location" in df.columns:
            sl = df["search_location"].fillna("")
            df = df[(sl == "") | (sl == cur_loc)]

if df.empty:
    if selected_config_id is None:
        st.info("No active jobs yet. Go to the home page, upload your resume, and search for jobs!")
    else:
        st.info(f"No jobs in **{config_label_for_caption}** yet — run a search from the home page.")
    st.stop()

# ── Hide & offer to delete jobs with bad URLs ─────────────────────────────────
# Older searches may have saved YouTube videos, Reddit threads, or generic
# "best jobs" articles before the URL filter was added. Hide them from view
# and let the user wipe them with one click.
if "job_link" in df.columns:
    url_ok = df["job_link"].fillna("").apply(_is_allowed_url)
    bad_df = df[~url_ok]
    df = df[url_ok]
    bad_count = len(bad_df)
    if bad_count > 0:
        warn_col, btn_col = st.columns([3, 1])
        warn_col.warning(
            f"**{bad_count} jobs hidden** because their URLs aren't real job postings "
            "(YouTube videos, blog posts, search-result pages from older searches)."
        )
        if btn_col.button("Delete them permanently", type="primary",
                          use_container_width=True):
            delete_jobs_by_ids([int(i) for i in bad_df["id"].tolist()])
            st.toast(f"Deleted {bad_count} bad-URL jobs.")
            st.rerun()

if df.empty:
    st.info("After filtering out bad-URL entries, no jobs remain. "
            "Use the home page to run a fresh search.")
    st.stop()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_applied(applied_date) -> bool:
    """Robust check that handles None, pd.NaT, empty strings, and 'NaT' literals."""
    try:
        if applied_date is None or pd.isna(applied_date):
            return False
    except (TypeError, ValueError):
        pass
    s = str(applied_date).strip().lower()
    return bool(s) and s not in ("nat", "none", "null", "nan")


def _status_of(row) -> tuple[str, str]:
    """Return (emoji, label) for the row's current status."""
    status = str(row.get("status") or "").strip().lower()
    comments = str(row.get("comments") or "").lower()
    flagged = any(kw in comments for kw in FLAG_KEYWORDS)

    if status == "pass":
        return ("🟢", "Pass")
    if status == "fail":
        return ("🔴", "Fail")
    if flagged:
        return ("⚠️", "Flagged")
    if status == "waiting" or _is_applied(row.get("applied_date")):
        return ("🟡", "Waiting")
    return ("⚪", "Not applied")


# ── Sidebar Filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")

job_types = ["All"]
if "job_type" in df.columns:
    job_types += sorted(df["job_type"].dropna().unique().tolist())
selected_type = st.sidebar.selectbox("Job Type", job_types)

status_filter = st.sidebar.selectbox(
    "Status",
    ["All", "Not applied", "Waiting", "Pass", "Fail", "Flagged"],
)

companies = ["All"]
if "company" in df.columns:
    companies += sorted(df["company"].dropna().unique().tolist())
selected_company = st.sidebar.selectbox("Company", companies)

keyword = st.sidebar.text_input("Keyword Search", placeholder="e.g. CRISPR, oncology...")

sort_by = st.sidebar.selectbox(
    "Sort by",
    ["Fit Score", "Newest First", "Company A-Z", "Applied (recent first)"],
)

view_mode = st.sidebar.radio(
    "View",
    ["Compact list", "Detailed diary"],
    help="Compact list = scan many jobs. Detailed diary = full notes per job.",
)

# ── Apply Filters ──────────────────────────────────────────────────────────────
filtered = df.copy()

if selected_type != "All" and "job_type" in filtered.columns:
    filtered = filtered[filtered["job_type"] == selected_type]

if status_filter != "All":
    labels = filtered.apply(lambda r: _status_of(r)[1], axis=1)
    filtered = filtered[labels == status_filter]

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
labels_all = df.apply(lambda r: _status_of(r)[1], axis=1)
applied_count = int((labels_all.isin(["Waiting", "Pass", "Fail"])).sum())
waiting_count = int((labels_all == "Waiting").sum())
pass_count = int((labels_all == "Pass").sum())
fail_count = int((labels_all == "Fail").sum())

s1, s2, s3, s4, s5, s6 = st.columns(6)
s1.metric("Total", total)
s2.metric("Applied", applied_count)
s3.metric("Waiting", waiting_count)
s4.metric("Pass", pass_count)
s5.metric("Fail", fail_count)
s6.metric("Showing", len(filtered))

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

st.markdown(
    "**Legend:** ⚪ not applied · 🟡 waiting · 🟢 pass · 🔴 fail · ⚠️ flagged"
)
st.markdown("")


# ── Render Jobs ────────────────────────────────────────────────────────────────

def _render_actions(job_id: int, status_label: str, key_prefix: str):
    """Contextual action buttons based on current status."""
    if status_label == "Not applied":
        if st.button("Mark Applied", key=f"{key_prefix}_apply_{job_id}",
                     use_container_width=True):
            mark_applied(job_id)
            st.rerun()
    elif status_label == "Waiting":
        c_pass, c_fail = st.columns(2)
        if c_pass.button("Pass ✓", key=f"{key_prefix}_pass_{job_id}",
                         use_container_width=True):
            set_job_status(job_id, "pass")
            st.rerun()
        if c_fail.button("Fail ✗", key=f"{key_prefix}_fail_{job_id}",
                         use_container_width=True):
            set_job_status(job_id, "fail")
            st.rerun()
    else:  # Pass / Fail / Flagged
        if st.button("Reset status", key=f"{key_prefix}_reset_{job_id}",
                     use_container_width=True):
            set_job_status(job_id, None)
            st.rerun()


if view_mode == "Compact list":
    h = st.columns([0.5, 2.2, 3.0, 1.5, 0.7, 1.1, 1.6, 0.5])
    h[0].markdown("**·**")
    h[1].markdown("**Company**")
    h[2].markdown("**Job Title**")
    h[3].markdown("**Location**")
    h[4].markdown("**Score / 100**")
    h[5].markdown("**Applied**")
    h[6].markdown("**Actions**")
    h[7].markdown("**·**")
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

        emoji, label = _status_of(row)

        c = st.columns([0.5, 2.2, 3.0, 1.5, 0.7, 1.1, 1.6, 0.5])
        c[0].markdown(f"{emoji}<br><span style='font-size:10px'>{label}</span>",
                      unsafe_allow_html=True)
        c[1].markdown(f"**{company}**")
        if job_link and str(job_link).strip():
            c[2].markdown(f"[{title}]({job_link})")
        else:
            c[2].markdown(title)
        c[3].markdown(location)
        c[4].markdown(f"{fit_score}/100" if fit_score is not None else "—")
        c[5].markdown(str(applied_date) if _is_applied(applied_date) else "—")

        with c[6]:
            _render_actions(job_id, label, key_prefix="q")

        with c[7]:
            if st.button("✕", key=f"q_hide_{job_id}", help="Remove from tracker"):
                hide_job(job_id)
                st.rerun()

        with st.expander("Notes", expanded=False):
            new_comment = st.text_area(
                "Notes",
                value=comments if comments else "",
                key=f"q_comment_{job_id}",
                label_visibility="collapsed",
                placeholder="Add notes (e.g. recruiter call set, interview scheduled, rejection received)...",
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

        emoji, label = _status_of(row)
        score_text = f"Score: {fit_score}/100" if fit_score is not None else ""

        with st.expander(
            f"{emoji} *{label}* · **{company}** — {title}  |  {location}  |  {job_type}  |  {score_text}",
            expanded=False,
        ):
            detail_col, action_col = st.columns([3, 1])

            with detail_col:
                st.markdown(f"**Status:** {emoji} {label}")
                st.markdown(f"**Job Title:** {title}")
                st.markdown(f"**Company:** {company}")
                st.markdown(f"**Location:** {location}")
                st.markdown(f"**Type:** {job_type}")
                st.markdown(f"**Fit Score:** {f'{fit_score}/100' if fit_score is not None else '—'}")
                st.markdown(f"**Salary:** {salary if salary else '—'}")
                st.markdown(f"**Skills:** {key_skills if key_skills else '—'}")
                st.markdown(f"**Posted:** {posted_date if posted_date else '—'}")
                st.markdown(f"**Added:** {added_on if added_on else '—'}")
                st.markdown(
                    f"**Applied:** {applied_date if _is_applied(applied_date) else 'Not yet'}"
                )

                if comments:
                    st.markdown(f"**Your Notes:** {comments}")

            with action_col:
                _render_actions(job_id, label, key_prefix="d")

                if job_link and str(job_link).strip():
                    st.link_button("Open Job Link", str(job_link), use_container_width=True)

                st.markdown("**Your Notes:**")
                new_comment = st.text_area(
                    "Notes",
                    value=comments if comments else "",
                    key=f"comment_{job_id}",
                    label_visibility="collapsed",
                    placeholder="Add notes... (e.g. recruiter call, interview scheduled)",
                    height=100,
                )
                if st.button("Save Notes", key=f"save_{job_id}", use_container_width=True):
                    update_job(job_id, {"comments": new_comment})
                    st.rerun()

                st.markdown("---")

                if st.button("Remove from Tracker", key=f"hide_{job_id}", use_container_width=True):
                    hide_job(job_id)
                    st.rerun()
