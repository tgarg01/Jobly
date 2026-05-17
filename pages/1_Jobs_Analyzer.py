"""Jobs Analyzer — visual breakdown of the active tracker.

Scoping mirrors the Job Board: a configuration selector in the sidebar
picks which tracker to analyze, and the same dynamic radius / location
filter (each job stores the radius+location it was found at) is applied
so the analyzer's totals match what the user actually sees on the board.
"""

from collections import Counter
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.constants import FLAG_KEYWORDS
from utils.db import list_configs, load_jobs

st.set_page_config(page_title="Jobs Analyzer — Jobly",
                   page_icon=":bar_chart:", layout="wide")
st.title(":bar_chart: Jobs Analyzer")
st.caption(
    "Visual breakdown of your tracker. Use the sidebar to pick which "
    "configuration to analyze — by default it matches the Job Board."
)

# ── Bootstrap from URL ────────────────────────────────────────────────────────
if "user_email" not in st.session_state:
    qp = st.query_params.get("u")
    if qp and "@" in qp:
        st.session_state["user_email"] = qp.strip().lower()
if "user_email" not in st.session_state:
    st.warning("Please sign in on the home page first.")
    st.stop()

user_email = st.session_state["user_email"]


# ── Helpers (mirrored from Job Board so totals agree) ─────────────────────────

def _is_applied(applied_date) -> bool:
    try:
        if applied_date is None or pd.isna(applied_date):
            return False
    except (TypeError, ValueError):
        pass
    s = str(applied_date).strip().lower()
    return bool(s) and s not in ("nat", "none", "null", "nan")


def _s(v) -> str:
    """Pandas-safe string: None / NaN / NaT → ''."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v)


def _status_of(row) -> str:
    status = str(row.get("status") or "").strip().lower()
    comments = str(row.get("comments") or "").lower()
    flagged = any(kw in comments for kw in FLAG_KEYWORDS)
    if status == "pass":
        return "Pass"
    if status == "fail":
        return "Fail"
    if flagged:
        return "Flagged"
    if status == "waiting" or _is_applied(row.get("applied_date")):
        return "Waiting"
    return "Not applied"


_KNOWN_BOARDS = (
    "linkedin.com", "indeed.com", "glassdoor.com", "lever.co",
    "greenhouse.io", "ziprecruiter.com", "monster.com", "wellfound.com",
    "builtin.com", "myworkdayjobs.com", "workday.com",
)


def _source(url: str) -> str:
    """Map a job_link URL to a friendly source label (host or job board name)."""
    try:
        host = urlparse(_s(url)).netloc.lower().replace("www.", "")
    except Exception:
        return "—"
    if not host:
        return "—"
    for known in _KNOWN_BOARDS:
        if known in host:
            return known
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else host


# ── Configuration scope (sidebar) ─────────────────────────────────────────────
try:
    configs = list_configs(user_email)
except Exception as e:
    st.error(f"Could not load configurations: {e}")
    st.stop()

config_options: list[tuple[str, int | None]] = (
    [("All configurations", None)] + [(c["name"], c["id"]) for c in configs]
)
labels = [opt[0] for opt in config_options]

default_idx = 0
active_id = st.session_state.get("active_config_id")
if active_id is not None:
    for i, (_, cid) in enumerate(config_options):
        if cid == active_id:
            default_idx = i
            break

st.sidebar.header("Scope")
selected_label = st.sidebar.selectbox(
    "Configuration", labels, index=default_idx, key="analyzer_config_picker",
)
selected_config_id = next(cid for label, cid in config_options if label == selected_label)

# ── Load + apply the same display filter Job Board uses ──────────────────────
df = load_jobs(active_only=True, user_email=user_email, config_id=selected_config_id)

scope_caption = selected_label
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
        rad_str = f" · {cur_radius} mi" if cur_radius else ""
        scope_caption = f"{active_cfg['name']}{rad_str}"

if df.empty:
    st.info(f"No jobs in **{scope_caption}** to analyze yet.")
    st.stop()

st.caption(f"Analyzing **{len(df)}** jobs in scope: {scope_caption}.")
df = df.copy()
df["_status"] = df.apply(_status_of, axis=1)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total = int(len(df))
applied = int((df["_status"].isin(["Waiting", "Pass", "Fail"])).sum())
waiting = int((df["_status"] == "Waiting").sum())
passed = int((df["_status"] == "Pass").sum())
failed = int((df["_status"] == "Fail").sum())
responded = passed + failed
response_rate = (responded / applied * 100) if applied else 0
pass_rate = (passed / responded * 100) if responded else 0
avg_score = 0.0
if "fit_score" in df.columns:
    scores = pd.to_numeric(df["fit_score"], errors="coerce").dropna()
    if not scores.empty:
        avg_score = float(scores.mean())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Jobs", total)
k2.metric("Applied", applied, help="Jobs with status Waiting, Pass, or Fail.")
k3.metric("Response Rate", f"{response_rate:.0f}%",
          help="(Pass + Fail) / Applied — how often you've heard back.")
k4.metric("Pass Rate", f"{pass_rate:.0f}%",
          help="Pass / (Pass + Fail) — of those that responded, how many advanced.")
k5.metric("Avg Fit Score", f"{avg_score:.0f}/100" if avg_score else "—")

st.markdown("---")

# ── Application funnel — the most actionable single chart ────────────────────
st.subheader("Application Funnel")
funnel_df = pd.DataFrame({
    "Stage": ["Discovered", "Applied", "Got Response", "Passed"],
    "Count": [total, applied, responded, passed],
})
fig_funnel = px.funnel(
    funnel_df, x="Count", y="Stage",
    color_discrete_sequence=["#636EFA"],
)
fig_funnel.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=260)
st.plotly_chart(fig_funnel, use_container_width=True)

st.markdown("---")

# ── Status mix + Fit score distribution ──────────────────────────────────────
row1_l, row1_r = st.columns(2)

with row1_l:
    st.subheader("Status Breakdown")
    status_counts = df["_status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    color_map = {
        "Not applied": "#B0B0B0",
        "Waiting": "#FECB52",
        "Pass": "#00CC96",
        "Fail": "#EF553B",
        "Flagged": "#AB63FA",
    }
    fig_status = px.pie(
        status_counts, names="Status", values="Count", hole=0.45,
        color="Status", color_discrete_map=color_map,
    )
    fig_status.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
    st.plotly_chart(fig_status, use_container_width=True)

with row1_r:
    st.subheader("Fit Score Distribution")
    if "fit_score" in df.columns:
        scores = pd.to_numeric(df["fit_score"], errors="coerce").dropna()
        if not scores.empty:
            fig_score = px.histogram(
                scores, nbins=10,
                color_discrete_sequence=["#00CC96"],
            )
            fig_score.update_layout(
                xaxis_title="Fit Score (out of 100)",
                yaxis_title="Jobs",
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
            )
            st.plotly_chart(fig_score, use_container_width=True)
            st.caption(
                f"Median {int(scores.median())}/100 · "
                f"Top quartile ≥ {int(scores.quantile(0.75))}/100"
            )
        else:
            st.caption("No fit score data.")
    else:
        st.caption("No fit score column.")

st.markdown("---")

# ── Top Companies + Top Sources ──────────────────────────────────────────────
row2_l, row2_r = st.columns(2)

with row2_l:
    st.subheader("Top 10 Companies")
    if "company" in df.columns:
        top_co = df["company"].apply(_s)
        top_co = top_co[top_co != ""].value_counts().head(10).reset_index()
        top_co.columns = ["Company", "Count"]
        if not top_co.empty:
            fig_co = px.bar(
                top_co, x="Count", y="Company", orientation="h",
                color_discrete_sequence=["#636EFA"],
            )
            fig_co.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=10, l=10, r=10), height=320,
            )
            st.plotly_chart(fig_co, use_container_width=True)
        else:
            st.caption("No company data.")

with row2_r:
    st.subheader("Where Your Jobs Come From")
    if "job_link" in df.columns:
        sources = df["job_link"].apply(_source)
        src_counts = sources[sources != "—"].value_counts().head(10).reset_index()
        src_counts.columns = ["Source", "Count"]
        if not src_counts.empty:
            fig_src = px.bar(
                src_counts, x="Count", y="Source", orientation="h",
                color_discrete_sequence=["#AB63FA"],
            )
            fig_src.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=10, l=10, r=10), height=320,
            )
            st.plotly_chart(fig_src, use_container_width=True)
        else:
            st.caption("No source data.")

st.markdown("---")

# ── Application activity over time + Top Locations ───────────────────────────
row3_l, row3_r = st.columns(2)

with row3_l:
    st.subheader("Applications Over Time")
    if "applied_date" in df.columns:
        applied_df = df[df["applied_date"].apply(_is_applied)].copy()
        if not applied_df.empty:
            applied_df["_d"] = pd.to_datetime(
                applied_df["applied_date"], errors="coerce"
            ).dt.date
            applied_df = applied_df.dropna(subset=["_d"])
            daily = applied_df.groupby("_d").size().reset_index(name="Applied")
            daily.columns = ["Date", "Applied"]
            daily = daily.sort_values("Date")
            fig_t = px.bar(
                daily, x="Date", y="Applied",
                color_discrete_sequence=["#00CC96"],
            )
            fig_t.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=320,
            )
            st.plotly_chart(fig_t, use_container_width=True)
            total_apps = int(daily["Applied"].sum())
            most_active = daily.loc[daily["Applied"].idxmax()]
            st.caption(
                f"{total_apps} total applications · busiest day: "
                f"{most_active['Date']} ({int(most_active['Applied'])} jobs)"
            )
        else:
            st.caption("No applications recorded yet — mark some jobs as Applied "
                       "in the Job Board.")
    else:
        st.caption("No application data yet.")

with row3_r:
    st.subheader("Top Locations")
    if "location" in df.columns:
        loc = df["location"].apply(_s)
        loc_counts = loc[loc != ""].value_counts().head(10).reset_index()
        loc_counts.columns = ["Location", "Count"]
        if not loc_counts.empty:
            fig_loc = px.bar(
                loc_counts, x="Count", y="Location", orientation="h",
                color_discrete_sequence=["#FECB52"],
            )
            fig_loc.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=10, l=10, r=10), height=320,
            )
            st.plotly_chart(fig_loc, use_container_width=True)
        else:
            st.caption("No location data — most postings don't include a parseable city.")

st.markdown("---")

# ── Top Skills + Salary visibility ───────────────────────────────────────────
row4_l, row4_r = st.columns(2)

with row4_l:
    st.subheader("Top Skills in Listings")
    if "key_skills" in df.columns and df["key_skills"].notna().any():
        all_skills: list[str] = []
        for skills_str in df["key_skills"].dropna():
            for skill in str(skills_str).split(","):
                cleaned = skill.strip()
                if cleaned:
                    all_skills.append(cleaned)
        if all_skills:
            skill_counts = Counter(all_skills).most_common(15)
            skill_df = pd.DataFrame(skill_counts, columns=["Skill", "Count"])
            fig_skills = px.bar(
                skill_df, x="Count", y="Skill", orientation="h",
                color="Count", color_continuous_scale="Teal",
            )
            fig_skills.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=10, l=10, r=10), height=400,
                showlegend=False,
            )
            st.plotly_chart(fig_skills, use_container_width=True)
        else:
            st.caption("No skill data yet.")
    else:
        st.caption("No skill data yet.")

with row4_r:
    st.subheader("Salary Visibility")
    if "salary" in df.columns:
        has_salary = df["salary"].apply(lambda x: bool(_s(x).strip()))
        salary_count = int(has_salary.sum())
        pct = (salary_count / total * 100) if total else 0
        st.metric("Listings with salary info", f"{salary_count} ({pct:.0f}%)")
        if salary_count > 0:
            sample_cols = [c for c in ("company", "job_title", "salary", "_status")
                           if c in df.columns]
            sample = (
                df[has_salary][sample_cols]
                .head(10)
                .rename(columns={"_status": "Status"})
            )
            st.dataframe(sample, use_container_width=True, hide_index=True)
        else:
            st.caption("None of the listings in scope include parseable salary info.")
    else:
        st.caption("No salary column.")
