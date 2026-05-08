"""Dashboard — summary cards, charts, and skill cloud."""

import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
from utils.db import load_jobs

st.set_page_config(page_title="Dashboard — Jobly", page_icon=":bar_chart:", layout="wide")
st.title(":bar_chart: Dashboard")

df = load_jobs(active_only=True)

if df.empty:
    st.info("No jobs in the tracker yet. Head to **Add Job** to get started!")
    st.stop()

# ── Summary Cards ──────────────────────────────────────────────────────────────
total = len(df)
applied = int(df["applied_date"].notna().sum()) if "applied_date" in df.columns else 0
pending = total - applied

# Count expired/irrelevant based on comments containing flag keywords
flag_keywords = ["expired", "irrelevant", "link not working", "no longer exists", "closed", "removed"]
flagged = 0
if "comments" in df.columns:
    for _, row in df.iterrows():
        c = str(row.get("comments", "") or "").lower()
        if any(kw in c for kw in flag_keywords):
            flagged += 1

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs", total)
c2.metric("Applied", applied)
c3.metric("Pending", pending)
c4.metric("Expired / Irrelevant", flagged)

st.markdown("---")

# ── Charts ─────────────────────────────────────────────────────────────────────
chart_left, chart_right = st.columns(2)

# Donut: Postdoc vs Industry
with chart_left:
    st.subheader("Job Type Split")
    if "job_type" in df.columns and df["job_type"].notna().any():
        type_counts = df["job_type"].value_counts().reset_index()
        type_counts.columns = ["Job Type", "Count"]
        fig_donut = px.pie(
            type_counts,
            names="Job Type",
            values="Count",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.caption("No job type data yet.")

# Bar: Jobs by company (top 10)
with chart_right:
    st.subheader("Top 10 Companies")
    if "company" in df.columns:
        top_companies = df["company"].value_counts().head(10).reset_index()
        top_companies.columns = ["Company", "Count"]
        fig_bar = px.bar(
            top_companies,
            x="Count",
            y="Company",
            orientation="h",
            color_discrete_sequence=["#636EFA"],
        )
        fig_bar.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.caption("No company data yet.")

st.markdown("---")

# Timeline: Jobs added over time
st.subheader("Jobs Added Over Time")
if "added_on" in df.columns and df["added_on"].notna().any():
    timeline_df = df.copy()
    timeline_df["added_on"] = pd.to_datetime(timeline_df["added_on"], errors="coerce")
    timeline_df = timeline_df.dropna(subset=["added_on"])
    daily = timeline_df.groupby("added_on").size().reset_index(name="Jobs Added")
    daily = daily.sort_values("added_on")
    fig_timeline = px.area(
        daily,
        x="added_on",
        y="Jobs Added",
        labels={"added_on": "Date"},
        color_discrete_sequence=["#00CC96"],
    )
    fig_timeline.update_layout(margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.caption("No timeline data available.")

st.markdown("---")

# Skill Cloud
st.subheader("Most Common Skills")
if "key_skills" in df.columns and df["key_skills"].notna().any():
    all_skills: list[str] = []
    for skills_str in df["key_skills"].dropna():
        for skill in str(skills_str).split(","):
            cleaned = skill.strip()
            if cleaned:
                all_skills.append(cleaned)
    if all_skills:
        skill_counts = Counter(all_skills).most_common(20)
        skill_df = pd.DataFrame(skill_counts, columns=["Skill", "Count"])
        fig_skills = px.bar(
            skill_df,
            x="Count",
            y="Skill",
            orientation="h",
            color="Count",
            color_continuous_scale="Teal",
        )
        fig_skills.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=False,
        )
        st.plotly_chart(fig_skills, use_container_width=True)
    else:
        st.caption("No skill data yet.")
else:
    st.caption("No skill data yet.")
