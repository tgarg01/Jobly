"""Add Job — manual entry form with duplicate check."""

import streamlit as st
from utils.db import insert_job, is_duplicate
from utils.constants import JOB_TYPES, DEFAULT_LOCATION

st.set_page_config(page_title="Add Job — Jobly", page_icon=":heavy_plus_sign:", layout="wide")
st.title(":heavy_plus_sign: Add Job")

st.markdown("Manually add a new job opportunity to your tracker.")

with st.form("add_job_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        company = st.text_input("Company *", placeholder="e.g. Genentech")
        job_title = st.text_input("Job Title *", placeholder="e.g. Postdoctoral Fellow – Oncology")
        location = st.text_input("Location", value=DEFAULT_LOCATION)
        job_type = st.selectbox("Job Type", JOB_TYPES)
        salary = st.text_input("Salary", placeholder="e.g. $65,000/yr (if listed)")

    with col2:
        job_link = st.text_input("Job Link", placeholder="https://...")
        posted_date = st.text_input("Posted Date", placeholder="e.g. 2026-05-07")
        contact_info = st.text_input("Contact Info", placeholder="PI email or recruiter name")
        key_skills = st.text_input("Key Skills", placeholder="e.g. CRISPR, tumor microenvironment, scRNA-seq")
        fit_score = st.slider("Fit Score (0–100)", min_value=0, max_value=100, value=50)

    comments = st.text_area("Comments", placeholder="Any notes about this position...")

    submitted = st.form_submit_button("Add Job", use_container_width=True)

    if submitted:
        if not company.strip() or not job_title.strip():
            st.error("Company and Job Title are required.")
        elif is_duplicate(company, job_title):
            st.warning(
                f"A job at **{company}** with title **{job_title}** already exists. "
                "Check the Job Board for duplicates."
            )
        else:
            row = {
                "company": company.strip(),
                "job_title": job_title.strip(),
                "location": location.strip() or None,
                "job_link": job_link.strip() or None,
                "posted_date": posted_date.strip() or None,
                "contact_info": contact_info.strip() or None,
                "job_type": job_type,
                "key_skills": key_skills.strip() or None,
                "comments": comments.strip() or None,
                "fit_score": fit_score,
                "salary": salary.strip() or None,
            }
            try:
                result = insert_job(row)
                st.success(f"Added **{job_title}** at **{company}**!")
            except Exception as e:
                st.error(f"Failed to insert job: {e}")
