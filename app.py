"""Jobly — Job Tracker with AI-powered search."""

import json
import streamlit as st

from utils.db import (
    get_user_profile, save_user_profile, delete_user_resume,
    list_configs, create_config, update_config, delete_config,
    clear_config_resume_override,
    insert_job, is_duplicate,
)
from utils.resume_parser import (
    extract_text, build_search_profile, extract_job_titles, build_queries,
)

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


# ── Trackers (configs): load + auto-create config-1 ───────────────────────────
def _next_config_name(existing: list[dict]) -> str:
    used = {c["name"] for c in existing}
    n = 1
    while f"config-{n}" in used:
        n += 1
    return f"config-{n}"


try:
    configs = list_configs(user_email)
except Exception as e:
    st.error(
        f"Could not load configurations from Supabase: {e}. "
        "Run supabase_schema.sql in the Supabase SQL editor and reload."
    )
    st.stop()

if not configs:
    try:
        create_config(user_email, "config-1")
    except Exception as e:
        st.error(f"Could not create config-1: {e}")
        st.stop()
    configs = list_configs(user_email)

config_ids = [c["id"] for c in configs]
if st.session_state.get("active_config_id") not in config_ids:
    st.session_state["active_config_id"] = configs[0]["id"]

active_config = next(c for c in configs if c["id"] == st.session_state["active_config_id"])


# ── Tracker selector (prominent, near top) ────────────────────────────────────
st.markdown("---")
st.subheader("📋 Active Tracker")

ADD_OPTION = "➕ New tracker"
config_names = [c["name"] for c in configs]
options = config_names + [ADD_OPTION]
default_idx = options.index(active_config["name"])

picked = st.radio(
    "Active tracker",
    options,
    index=default_idx,
    horizontal=True,
    label_visibility="collapsed",
)

if picked == ADD_OPTION:
    try:
        new_name = _next_config_name(configs)
        new = create_config(user_email, new_name)
        st.session_state["active_config_id"] = new["id"]
        st.rerun()
    except Exception as e:
        st.error(f"Could not create new tracker: {e}")
elif picked != active_config["name"]:
    new_active = next(c for c in configs if c["name"] == picked)
    st.session_state["active_config_id"] = new_active["id"]
    st.rerun()

st.caption(
    f"Editing **{active_config['name']}**. Each tracker is independent — "
    "its own location, optional resume, and job list. "
    "To search a different location, create a new tracker."
)

# Delete tracker (only when more than one exists)
if len(configs) > 1:
    if st.button(
        f"🗑 Delete {active_config['name']} and all its jobs",
        type="secondary",
    ):
        st.session_state["confirm_delete_cfg"] = True

if st.session_state.get("confirm_delete_cfg"):
    st.warning(
        f"Delete **{active_config['name']}** and every job inside it? "
        "This cannot be undone."
    )
    d_yes, d_no = st.columns([1, 4])
    if d_yes.button("Yes, delete forever", type="primary"):
        delete_config(active_config["id"])
        st.session_state.pop("active_config_id", None)
        st.session_state.pop("confirm_delete_cfg", None)
        st.rerun()
    if d_no.button("Cancel"):
        st.session_state.pop("confirm_delete_cfg", None)
        st.rerun()


# ── Effective resume for active tracker ───────────────────────────────────────
profile_data = get_user_profile(user_email)
main_skills: list[str] = []
main_titles: list[str] = []
if profile_data:
    try:
        main_skills = json.loads(profile_data.get("skills", "[]") or "[]")
        main_titles = json.loads(profile_data.get("titles", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    if not main_titles and profile_data.get("resume_text"):
        main_titles = extract_job_titles(profile_data["resume_text"])

override_resume_text = active_config.get("override_resume_text")
override_skills: list[str] = []
override_titles: list[str] = []
try:
    override_skills = json.loads(active_config.get("override_skills", "[]") or "[]")
    override_titles = json.loads(active_config.get("override_titles", "[]") or "[]")
except (json.JSONDecodeError, TypeError):
    pass

if override_resume_text:
    eff_resume_text = override_resume_text
    eff_filename = active_config.get("override_resume_filename")
    eff_cl_filename = active_config.get("override_cover_letter_filename")
    eff_skills = override_skills
    eff_titles = override_titles
    eff_source = "override"
else:
    eff_resume_text = profile_data.get("resume_text") if profile_data else None
    eff_filename = profile_data.get("resume_filename") if profile_data else None
    eff_cl_filename = profile_data.get("cover_letter_filename") if profile_data else None
    eff_skills = main_skills
    eff_titles = main_titles
    eff_source = "main"

has_effective_resume = bool(eff_resume_text)


# ── Resume Section ────────────────────────────────────────────────────────────
def show_upload_form(user_email: str, active_config: dict):
    upload_col1, upload_col2 = st.columns(2)
    with upload_col1:
        resume_file = st.file_uploader("Resume *", type=["pdf", "docx", "txt"], key="resume_uploader")
    with upload_col2:
        cl_file = st.file_uploader("Cover Letter (optional)", type=["pdf", "docx", "txt"], key="cl_uploader")

    save_as_override = st.checkbox(
        f"Use this resume only for the **{active_config['name']}** tracker",
        value=False,
        help=("If unchecked, this is your main resume — used by every tracker "
              "that doesn't have its own override."),
    )

    if st.button("Save & Process", type="primary", use_container_width=True):
        if not resume_file:
            st.error("Please upload your resume.")
            return

        resume_bytes = resume_file.read()
        resume_text = extract_text(resume_bytes, resume_file.name)

        cl_text = ""
        cl_filename = ""
        if cl_file:
            cl_bytes = cl_file.read()
            cl_text = extract_text(cl_bytes, cl_file.name)
            cl_filename = cl_file.name

        if not resume_text:
            st.error("Could not extract text. Try a different file format.")
            return

        profile = build_search_profile(resume_text, cl_text)

        try:
            if save_as_override:
                update_config(active_config["id"], {
                    "override_resume_text": resume_text,
                    "override_cover_letter_text": cl_text or None,
                    "override_resume_filename": resume_file.name,
                    "override_cover_letter_filename": cl_filename or None,
                    "override_skills": json.dumps(profile["skills"]),
                    "override_titles": json.dumps(profile["titles"]),
                })
            else:
                save_user_profile(
                    email=user_email,
                    resume_text=resume_text,
                    cover_letter_text=cl_text,
                    resume_filename=resume_file.name,
                    cover_letter_filename=cl_filename,
                    skills=profile["skills"],
                    search_queries=profile["queries"],
                    titles=profile["titles"],
                )
        except Exception as e:
            st.error(
                f"Could not save resume: {e}. "
                "Check that supabase_schema.sql has been run."
            )
            return

        st.session_state.pop("show_upload", None)
        scope = active_config["name"] if save_as_override else "main resume (all trackers)"
        st.success(
            f"Saved! {len(profile['skills'])} skills, "
            f"{len(profile['titles'])} candidate titles. Scope: {scope}."
        )
        st.rerun()


st.markdown("---")
if has_effective_resume and not st.session_state.get("show_upload", False):
    st.header("Resume")
    if eff_source == "override":
        st.caption(f"Using a resume specific to **{active_config['name']}**.")
    else:
        st.caption("Using your main resume — shared by all trackers without an override.")

    col_info, col_action = st.columns([3, 1])
    with col_info:
        st.success(f"Resume loaded: **{eff_filename}**")
        if eff_cl_filename:
            st.info(f"Cover letter: **{eff_cl_filename}**")
        with st.expander("Profile summary", expanded=False):
            st.markdown(f"**Skills:** {', '.join(eff_skills[:15]) or '—'}")
            st.markdown(f"**Detected titles:** {', '.join(eff_titles[:8]) or '—'}")
    with col_action:
        if st.button("Upload New Resume", use_container_width=True):
            st.session_state["show_upload"] = True
            st.rerun()
        if eff_source == "override":
            if st.button("Use Main Resume", use_container_width=True,
                         help="Drop this tracker's override and fall back to your main resume."):
                clear_config_resume_override(active_config["id"])
                st.rerun()
        else:
            if st.button("Remove Documents", use_container_width=True):
                delete_user_resume(user_email)
                st.rerun()
else:
    if has_effective_resume:
        st.header("Replace Resume")
    else:
        st.header("Upload Your Resume")
        st.caption("Upload a resume to enable AI-powered job search. It'll be saved.")

    show_upload_form(user_email, active_config)

    if st.session_state.get("show_upload") and st.button("Cancel"):
        st.session_state.pop("show_upload", None)
        st.rerun()


# ── Search section ────────────────────────────────────────────────────────────
def _location_for_query(loc: str, radius: int | None) -> str:
    if not loc:
        return "United States"
    if radius and radius > 0 and "remote" not in loc.lower():
        return f"within {radius} miles of {loc}"
    return loc


def _run_search(location: str, radius: int | None, *, config_id: int, config_name: str,
                eff_skills: list[str], eff_titles: list[str]):
    from utils.job_search import search_jobs

    location_for_search = _location_for_query(location, radius)
    queries = build_queries(eff_skills, eff_titles, [location_for_search])
    if not queries:
        st.error("Couldn't build any queries. Re-upload your resume so we can detect skills/titles.")
        return

    status_box = st.empty()
    status_box.info(f"Starting search for **{config_name}** ({location_for_search})...")

    jobs = search_jobs(
        queries=queries,
        user_skills=eff_skills,
        max_results_per_query=10,
        status_container=status_box,
        user_email=user_email,
    )

    if not jobs:
        status_box.warning(
            "No jobs found this time. The free DuckDuckGo search rate-limits "
            "frequent requests. Wait 1–2 minutes and try again."
        )
        return

    status_box.info(f"Found {len(jobs)} jobs. Saving new ones into **{config_name}**...")
    added = skipped = failed = 0
    last_error = ""
    progress = st.progress(0)

    for i, job in enumerate(jobs):
        progress.progress((i + 1) / len(jobs))
        try:
            if is_duplicate(job["company"], job["job_title"],
                            user_email=user_email, config_id=config_id):
                skipped += 1
                continue
            job["config_id"] = config_id
            insert_job(job)
            added += 1
        except Exception as e:
            failed += 1
            last_error = f"{type(e).__name__}: {str(e)[:160]}"

    progress.empty()
    if added > 0:
        status_box.success(
            f"Done! Added **{added}** new jobs to **{config_name}**. "
            f"({skipped} duplicates skipped, {failed} failed.) "
            "Open the **Job Board** in the sidebar to manage them."
        )
    else:
        status_box.error(
            f"Search ran but nothing was saved. {skipped} duplicates, {failed} failed. "
            + (f"Last error: {last_error}" if last_error else
               "If this keeps happening, re-run supabase_schema.sql.")
        )


st.markdown("---")
st.header("Search Jobs")

saved_loc = active_config.get("location")
saved_radius = active_config.get("radius_miles")

if not has_effective_resume:
    st.info("Upload a resume above to enable job search.")

elif saved_loc:
    # Locked view: location was committed on first search.
    rad_str = f" · within **{saved_radius}** miles" if saved_radius else ""
    st.success(f"📍 Location: **{saved_loc}**{rad_str}")
    st.caption(
        f"Location is locked for **{active_config['name']}**. "
        "To search a different location, click **➕ New tracker** above to create another."
    )
    if st.button("Run Search Again", type="primary", use_container_width=True):
        _run_search(
            saved_loc, saved_radius,
            config_id=active_config["id"], config_name=active_config["name"],
            eff_skills=eff_skills, eff_titles=eff_titles,
        )

else:
    # Unlocked: prompt for location + radius.
    location_input = st.text_input(
        "Where do you want to search?",
        placeholder="e.g. San Jose, CA  ·  California  ·  London, UK  ·  Remote",
        key=f"loc_input_{active_config['id']}",
    )
    radius = st.slider(
        "Radius (miles)",
        min_value=0, max_value=100, value=25, step=5,
        key=f"radius_input_{active_config['id']}",
        help="Use 0 for state-wide, country-wide, or remote searches.",
    )

    can_search = bool(location_input.strip())
    if st.button("Search Jobs Now", type="primary", use_container_width=True,
                 disabled=not can_search):
        loc = location_input.strip()
        rad = radius if radius > 0 else None
        # Lock the tracker's location/radius before running search.
        try:
            update_config(active_config["id"], {"location": loc, "radius_miles": rad})
        except Exception as e:
            st.error(f"Could not save location to tracker: {e}")
            st.stop()
        _run_search(
            loc, rad,
            config_id=active_config["id"], config_name=active_config["name"],
            eff_skills=eff_skills, eff_titles=eff_titles,
        )

st.markdown("---")
st.markdown(
    """
    ### Pages
    - **Dashboard** — Stats & charts
    - **Job Board** — Tracker diary scoped to the active tracker (or all)
    """
)
st.caption("Built with Streamlit + Supabase")
