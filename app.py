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

# ── Resume & Cover Letter Upload ───────────────────────────────────────────────
st.header("Upload Your Documents")
st.caption("Upload your resume and/or cover letter to power AI-driven job search.")

upload_col1, upload_col2 = st.columns(2)

with upload_col1:
    resume_file = st.file_uploader(
        "Resume",
        type=["pdf", "docx", "txt"],
        key="resume_upload",
        help="Upload your resume (PDF, DOCX, or TXT)",
    )

with upload_col2:
    cover_letter_file = st.file_uploader(
        "Cover Letter (optional)",
        type=["pdf", "docx", "txt"],
        key="cover_letter_upload",
        help="Upload your cover letter for better matching",
    )

# Process uploaded files
if resume_file is not None:
    from utils.resume_parser import extract_text, build_search_profile

    resume_bytes = resume_file.read()
    resume_text = extract_text(resume_bytes, resume_file.name)

    cover_letter_text = ""
    if cover_letter_file is not None:
        cl_bytes = cover_letter_file.read()
        cover_letter_text = extract_text(cl_bytes, cover_letter_file.name)

    if resume_text:
        profile = build_search_profile(resume_text, cover_letter_text)
        st.session_state["search_profile"] = profile
        st.session_state["user_skills"] = profile["skills"]

        with st.expander("Your Extracted Profile", expanded=False):
            st.markdown(f"**Skills detected:** {', '.join(profile['skills'][:15]) if profile['skills'] else 'None found'}")
            st.markdown(f"**Job titles found:** {', '.join(profile['titles'][:5]) if profile['titles'] else 'None found'}")
            st.markdown(f"**Locations:** {', '.join(profile['locations'])}")
            st.markdown(f"**Search queries to run:** {len(profile['queries'])}")

        st.success(f"Resume processed! Found {len(profile['skills'])} skills and {len(profile['queries'])} search queries.")
    else:
        st.error("Could not extract text from the uploaded file. Please try a different format.")

st.markdown("---")

# ── Job Search Button ──────────────────────────────────────────────────────────
st.header("Search for Jobs")

if "search_profile" not in st.session_state:
    st.info("Upload your resume above to enable job search.")
else:
    profile = st.session_state["search_profile"]
    user_skills = st.session_state.get("user_skills", [])

    st.caption(
        f"Ready to search across LinkedIn, Indeed, Glassdoor & more using "
        f"{len(profile['queries'])} queries based on your profile."
    )

    if st.button("Search Jobs Now", type="primary", use_container_width=True):
        from utils.job_search import search_jobs
        from utils.db import load_jobs, insert_job, is_duplicate

        with st.spinner("Searching across job boards... This may take a minute."):
            jobs = search_jobs(
                queries=profile["queries"],
                user_skills=user_skills,
                max_results_per_query=15,
            )

        if not jobs:
            st.warning("No jobs found. Try adjusting your resume or uploading a more detailed one.")
        else:
            st.info(f"Found {len(jobs)} potential jobs. Saving new ones to your tracker...")

            added = 0
            skipped = 0
            progress = st.progress(0)

            for i, job in enumerate(jobs):
                progress.progress((i + 1) / len(jobs))
                try:
                    if not is_duplicate(job["company"], job["job_title"]):
                        insert_job(job)
                        added += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

            progress.empty()
            st.success(
                f"Done! Added **{added}** new jobs to your tracker. "
                f"({skipped} duplicates or errors skipped.)"
            )
            st.info("Head to the **Job Board** page to browse and manage your jobs!")

st.markdown("---")

# ── Navigation Guide ───────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ### Pages
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
        1. Upload your **resume** above
        2. Click **Search Jobs Now** to find matches
        3. Use the **Job Board** to mark jobs as applied
        4. Check **Insights** to export or review flagged listings
        """
    )

st.markdown("---")
st.caption("Built with Streamlit + Supabase")
