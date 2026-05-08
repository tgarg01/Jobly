"""Jobly — Job Tracker with AI-powered search."""

import json
import streamlit as st
from utils.db import get_user_profile, save_user_profile, delete_user_resume
from utils.resume_parser import extract_text, build_search_profile

st.set_page_config(
    page_title="Jobly — Job Tracker",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Session bootstrap from URL ────────────────────────────────────────────────
# Streamlit clears session_state on browser refresh, so we keep the user's
# email in the URL query params. That way refresh keeps them signed in and
# their saved resume stays loaded.
if "user_email" not in st.session_state:
    qp_email = st.query_params.get("u")
    if qp_email and "@" in qp_email:
        st.session_state["user_email"] = qp_email.strip().lower()


# ── Helper: Upload Form ───────────────────────────────────────────────────────
def show_upload_form(user_email: str):
    """Render the resume/cover letter upload form."""
    upload_col1, upload_col2 = st.columns(2)

    with upload_col1:
        resume_file = st.file_uploader(
            "Resume *",
            type=["pdf", "docx", "txt"],
            key="resume_uploader",
            help="Upload your resume (PDF, DOCX, or TXT)",
        )

    with upload_col2:
        cover_letter_file = st.file_uploader(
            "Cover Letter (optional)",
            type=["pdf", "docx", "txt"],
            key="cl_uploader",
            help="Upload your cover letter for better matching",
        )

    if st.button("Save & Process", type="primary", use_container_width=True):
        if not resume_file:
            st.error("Please upload your resume.")
            return

        resume_bytes = resume_file.read()
        resume_text = extract_text(resume_bytes, resume_file.name)

        cover_letter_text = ""
        cl_filename = ""
        if cover_letter_file:
            cl_bytes = cover_letter_file.read()
            cover_letter_text = extract_text(cl_bytes, cover_letter_file.name)
            cl_filename = cover_letter_file.name

        if not resume_text:
            st.error("Could not extract text from the resume. Try a different file format.")
            return

        profile = build_search_profile(resume_text, cover_letter_text)

        try:
            save_user_profile(
                email=user_email,
                resume_text=resume_text,
                cover_letter_text=cover_letter_text,
                resume_filename=resume_file.name,
                cover_letter_filename=cl_filename,
                skills=profile["skills"],
                search_queries=profile["queries"],
            )
        except Exception as e:
            st.error(
                f"Could not save resume to the database: {e}. "
                "Check your Supabase connection and that the `user_profiles` table exists."
            )
            return

        st.session_state["user_skills"] = profile["skills"]
        st.session_state["search_queries"] = profile["queries"]
        st.session_state.pop("show_upload", None)

        st.success(
            f"Resume saved! Found {len(profile['skills'])} skills and "
            f"{len(profile['queries'])} search queries. "
            "It will stay loaded next time you sign in with this email."
        )
        st.rerun()


# ── Email Login ────────────────────────────────────────────────────────────────
if "user_email" not in st.session_state:
    st.title(":briefcase: Jobly")
    st.subheader("Your AI-Powered Job Tracker")
    st.markdown("---")

    st.markdown("### Sign in to get started")
    email_input = st.text_input("Enter your email address", placeholder="you@example.com")

    if st.button("Continue", type="primary", use_container_width=True):
        if email_input and "@" in email_input:
            email = email_input.strip().lower()
            st.session_state["user_email"] = email
            st.query_params["u"] = email
            st.rerun()
        else:
            st.error("Please enter a valid email address.")

    st.caption(
        "Your email is used to save your resume and job data — no password needed. "
        "Once you upload your resume it stays linked to this email."
    )
    st.stop()

# ── Logged In ──────────────────────────────────────────────────────────────────
user_email = st.session_state["user_email"]
# Make sure the URL reflects the current user so refresh keeps them in.
if st.query_params.get("u") != user_email:
    st.query_params["u"] = user_email

with st.sidebar:
    st.markdown(f"**Logged in as:** {user_email}")
    if st.button("Log out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.query_params.clear()
        st.rerun()

st.title(":briefcase: Jobly")
st.caption(f"Welcome back, {user_email.split('@')[0]}!")

# ── Load Saved Profile ────────────────────────────────────────────────────────
profile_data = get_user_profile(user_email)
has_saved_resume = profile_data and profile_data.get("resume_text")

# ── Resume Section ─────────────────────────────────────────────────────────────
st.markdown("---")

if has_saved_resume and not st.session_state.get("show_upload", False):
    st.header("Your Resume")

    saved_skills = []
    saved_queries = []
    try:
        saved_skills = json.loads(profile_data.get("skills", "[]") or "[]")
        saved_queries = json.loads(profile_data.get("search_queries", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    col_info, col_action = st.columns([3, 1])

    with col_info:
        st.success(f"Resume loaded: **{profile_data.get('resume_filename', 'resume')}**")
        if profile_data.get("cover_letter_filename"):
            st.info(f"Cover letter: **{profile_data.get('cover_letter_filename')}**")

        with st.expander("Your Profile Summary", expanded=False):
            st.markdown(f"**Skills:** {', '.join(saved_skills[:15]) if saved_skills else '—'}")
            st.markdown(f"**Search queries ready:** {len(saved_queries)}")

    with col_action:
        if st.button("Upload New Resume", use_container_width=True):
            st.session_state["show_upload"] = True
            st.rerun()
        if st.button("Remove Documents", use_container_width=True):
            delete_user_resume(user_email)
            for k in ("user_skills", "search_queries", "show_upload"):
                st.session_state.pop(k, None)
            st.rerun()

    st.session_state["user_skills"] = saved_skills
    st.session_state["search_queries"] = saved_queries

else:
    if has_saved_resume:
        st.header("Replace Your Documents")
    else:
        st.header("Upload Your Resume")
        st.caption("Upload your resume to enable AI-powered job search. It will be saved for next time.")

    show_upload_form(user_email)

    if st.session_state.get("show_upload") and st.button("Cancel"):
        st.session_state.pop("show_upload", None)
        st.rerun()

st.markdown("---")

# ── Job Search ─────────────────────────────────────────────────────────────────
st.header("Search for Jobs")

user_skills = st.session_state.get("user_skills", [])
search_queries = st.session_state.get("search_queries", [])

if not search_queries:
    st.info("Upload your resume above to enable job search.")
else:
    st.caption(
        f"Ready to search LinkedIn, Indeed, Glassdoor & more using "
        f"{len(search_queries)} queries based on your profile."
    )

    if st.button("Search Jobs Now", type="primary", use_container_width=True):
        from utils.job_search import search_jobs
        from utils.db import insert_job, is_duplicate

        status_box = st.empty()
        status_box.info("Starting job search...")

        jobs = search_jobs(
            queries=search_queries,
            user_skills=user_skills,
            max_results_per_query=10,
            status_container=status_box,
            user_email=user_email,
        )

        if not jobs:
            status_box.warning(
                "No jobs found this time. The free DuckDuckGo search service rate-limits "
                "frequent requests. Wait 1–2 minutes and try again."
            )
        else:
            status_box.info(f"Found {len(jobs)} jobs. Saving new ones to your tracker...")
            added = 0
            skipped = 0
            failed = 0
            last_error = ""
            progress = st.progress(0)

            for i, job in enumerate(jobs):
                progress.progress((i + 1) / len(jobs))
                try:
                    if is_duplicate(job["company"], job["job_title"], user_email=user_email):
                        skipped += 1
                        continue
                    insert_job(job)
                    added += 1
                except Exception as e:
                    failed += 1
                    last_error = f"{type(e).__name__}: {str(e)[:160]}"

            progress.empty()

            if added > 0:
                status_box.success(
                    f"Done! Added **{added}** new jobs to your tracker. "
                    f"({skipped} duplicates skipped, {failed} failed.) "
                    "Open the **Job Board** in the sidebar to manage them."
                )
            else:
                status_box.error(
                    f"Search ran but nothing was saved. "
                    f"{skipped} were duplicates, {failed} failed to insert. "
                    + (f"Last error: {last_error}" if last_error else
                       "If this keeps happening, check that the `jobs` table exists in Supabase "
                       "and includes a `user_email` column.")
                )

st.markdown("---")
st.markdown(
    """
    ### Pages
    - **Dashboard** — Stats & charts overview
    - **Job Board** — Your tracker diary: list, filter, take notes, mark applied
    """
)
st.caption("Built with Streamlit + Supabase")
