"""Jobly — Job Tracker with AI-powered search."""

import json
import streamlit as st
from utils.db import (
    get_user_profile,
    save_user_profile,
    delete_user_resume,
    save_preferred_location,
)
from utils.resume_parser import extract_text, build_search_profile, extract_job_titles
from utils.locations import US_STATES, MAJOR_CITIES, REMOTE_LABEL

st.set_page_config(
    page_title="Jobly — Job Tracker",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Session bootstrap from URL ────────────────────────────────────────────────
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
                titles=profile["titles"],
                preferred_location=st.session_state.get("preferred_location"),
            )
        except Exception as e:
            st.error(
                f"Could not save resume to the database: {e}. "
                "Check your Supabase connection and that the `user_profiles` table exists."
            )
            return

        st.session_state["user_skills"] = profile["skills"]
        st.session_state["user_titles"] = profile["titles"]
        st.session_state["search_queries"] = profile["queries"]
        st.session_state.pop("show_upload", None)

        st.success(
            f"Resume saved! Found {len(profile['skills'])} skills and "
            f"{len(profile['titles'])} candidate titles. "
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

saved_skills: list[str] = []
saved_titles: list[str] = []
saved_queries: list[str] = []
saved_pref_loc: str | None = None

if profile_data:
    try:
        saved_skills = json.loads(profile_data.get("skills", "[]") or "[]")
        saved_queries = json.loads(profile_data.get("search_queries", "[]") or "[]")
        saved_titles = json.loads(profile_data.get("titles", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    saved_pref_loc = profile_data.get("preferred_location")

    # Backfill titles for users who saved a resume before this column existed.
    if not saved_titles and profile_data.get("resume_text"):
        saved_titles = extract_job_titles(profile_data["resume_text"])

if has_saved_resume and not st.session_state.get("show_upload", False):
    st.header("Your Resume")

    col_info, col_action = st.columns([3, 1])

    with col_info:
        st.success(f"Resume loaded: **{profile_data.get('resume_filename', 'resume')}**")
        if profile_data.get("cover_letter_filename"):
            st.info(f"Cover letter: **{profile_data.get('cover_letter_filename')}**")

        with st.expander("Your Profile Summary", expanded=False):
            st.markdown(f"**Skills:** {', '.join(saved_skills[:15]) if saved_skills else '—'}")
            st.markdown(f"**Detected titles:** {', '.join(saved_titles[:8]) if saved_titles else '—'}")

    with col_action:
        if st.button("Upload New Resume", use_container_width=True):
            st.session_state["show_upload"] = True
            st.rerun()
        if st.button("Remove Documents", use_container_width=True):
            delete_user_resume(user_email)
            for k in ("user_skills", "user_titles", "search_queries", "show_upload"):
                st.session_state.pop(k, None)
            st.rerun()

    st.session_state["user_skills"] = saved_skills
    st.session_state["user_titles"] = saved_titles
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

# ── Location Filter (just below the resume block) ─────────────────────────────
st.markdown("---")
st.header("Search Location")
st.caption("Pick where you want to search. Switching here re-builds your queries — "
           "the same resume can target different markets.")

default_loc = st.session_state.get("preferred_location") or saved_pref_loc

def _initial_mode(loc: str | None) -> str:
    if not loc:
        return "Major City"
    if loc == REMOTE_LABEL:
        return "Remote"
    if loc in MAJOR_CITIES:
        return "Major City"
    if loc in US_STATES:
        return "State"
    return "Custom"

mode_options = ["Major City", "State", "Remote", "Custom"]
mode = st.radio(
    "Location type",
    mode_options,
    index=mode_options.index(_initial_mode(default_loc)),
    horizontal=True,
    key="loc_mode",
)

selected_location: str | None = None

if mode == "Major City":
    idx = MAJOR_CITIES.index(default_loc) if default_loc in MAJOR_CITIES else 0
    selected_location = st.selectbox("City", MAJOR_CITIES, index=idx, key="loc_city")
elif mode == "State":
    default_state = default_loc if default_loc in US_STATES else "California"
    selected_location = st.selectbox(
        "State", US_STATES, index=US_STATES.index(default_state), key="loc_state",
    )
elif mode == "Remote":
    selected_location = REMOTE_LABEL
    st.info("Searches will target remote roles in the United States.")
else:
    selected_location = st.text_input(
        "Custom location",
        value=default_loc if default_loc and default_loc not in MAJOR_CITIES + US_STATES + [REMOTE_LABEL] else "",
        placeholder="e.g. Boulder, CO or London, UK",
        key="loc_custom",
    )

st.session_state["preferred_location"] = selected_location

# ── Job Search ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.header("Search for Jobs")

user_skills = st.session_state.get("user_skills", [])
user_titles = st.session_state.get("user_titles", [])

if not has_saved_resume:
    st.info("Upload your resume above to enable job search.")
elif not selected_location:
    st.info("Pick a location above to enable job search.")
else:
    # Build the queries fresh from the chosen location so the user sees
    # exactly what we'll run.
    from utils.resume_parser import build_queries
    location_for_search = "Remote United States" if selected_location == REMOTE_LABEL else selected_location
    live_queries = build_queries(user_skills, user_titles, [location_for_search])

    st.caption(
        f"Will run **{len(live_queries)}** searches across LinkedIn, Indeed, Glassdoor & more "
        f"targeting **{selected_location}**."
    )
    with st.expander("Preview queries", expanded=False):
        for q in live_queries:
            st.markdown(f"- {q}")

    if st.button("Search Jobs Now", type="primary", use_container_width=True):
        from utils.job_search import search_jobs
        from utils.db import insert_job, is_duplicate

        # Persist preferred location (best effort).
        try:
            save_preferred_location(user_email, selected_location)
        except Exception:
            pass

        if not live_queries:
            st.error("Couldn't build any queries — re-upload your resume so we can detect skills/titles.")
            st.stop()

        status_box = st.empty()
        status_box.info("Starting job search...")

        jobs = search_jobs(
            queries=live_queries,
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
    - **Job Board** — Your tracker diary: list, filter, take notes, mark applied / pass / fail
    """
)
st.caption("Built with Streamlit + Supabase")
