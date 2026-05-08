"""Insights — flagged jobs, application funnel, CSV export."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.db import load_jobs
from utils.constants import FLAG_KEYWORDS

st.set_page_config(page_title="Insights — Jobly", page_icon=":mag:", layout="wide")
st.title(":mag: Insights")

df = load_jobs(active_only=True)
df_all = load_jobs(active_only=False)

if df_all.empty:
    st.info("No jobs in the tracker yet.")
    st.stop()

# ── Flagged Jobs ───────────────────────────────────────────────────────────────
st.subheader("Flagged Jobs for Cleanup")
st.caption("Jobs with comments containing: " + ", ".join(f'"{kw}"' for kw in FLAG_KEYWORDS))

flagged_mask = pd.Series(False, index=df.index)
if "comments" in df.columns:
    for kw in FLAG_KEYWORDS:
        flagged_mask = flagged_mask | df["comments"].fillna("").str.lower().str.contains(kw, na=False)

flagged_df = df[flagged_mask]

if flagged_df.empty:
    st.success("No flagged jobs. Everything looks clean!")
else:
    display_cols = ["company", "job_title", "comments", "applied_date", "job_link"]
    available_cols = [c for c in display_cols if c in flagged_df.columns]
    st.dataframe(flagged_df[available_cols], use_container_width=True, hide_index=True)

st.markdown("---")

# ── Application Funnel ─────────────────────────────────────────────────────────
st.subheader("Application Funnel")

total_added = len(df_all)
total_active = len(df)
total_applied = int(df_all["applied_date"].notna().sum()) if "applied_date" in df_all.columns else 0
total_hidden = total_added - total_active

fig_funnel = go.Figure(go.Funnel(
    y=["Added", "Active", "Applied", "Hidden / Removed"],
    x=[total_added, total_active, total_applied, total_hidden],
    textinfo="value+percent initial",
    marker=dict(color=["#636EFA", "#00CC96", "#EF553B", "#AB63FA"]),
))
fig_funnel.update_layout(margin=dict(t=20, b=20, l=20, r=20))
st.plotly_chart(fig_funnel, use_container_width=True)

st.markdown("---")

# ── CSV Export ─────────────────────────────────────────────────────────────────
st.subheader("Export Active Jobs")

if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Active Jobs as CSV",
        data=csv,
        file_name="active_jobs_export.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.caption("No active jobs to export.")
