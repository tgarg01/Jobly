"""Jobly — Taruna's Job Tracker"""

import streamlit as st

st.set_page_config(
    page_title="Jobly — Job Tracker",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title(":briefcase: Jobly")
st.subheader("Taruna's Cancer Biology & Oncology Job Tracker")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ### Welcome!
        Use the sidebar to navigate between pages:

        - **Dashboard** — Overview stats & charts
        - **Job Board** — Browse, filter & manage jobs
        - **Add Job** — Manually add a new opportunity
        - **Insights** — Flagged jobs, funnel & CSV export
        """
    )

with col2:
    st.markdown(
        """
        ### Quick Start
        1. Check the **Dashboard** for a snapshot of your pipeline
        2. Use the **Job Board** to mark jobs as applied or add comments
        3. Head to **Insights** to export your data or review flagged listings
        """
    )

st.markdown("---")
st.caption("Built with Streamlit + Supabase")
