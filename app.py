"""Jobly — Job Tracker with AI-powered search."""

import json
import streamlit as st

from utils.db import (
    get_user_profile, save_user_profile, delete_user_resume,
    list_configs, create_config, update_config, delete_config,
    clear_config_resume_override,
)
from utils.resume_parser import (
    extract_text, build_search_profile, extract_job_titles, build_queries,
)
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

# ── Load user profile (main resume) ───────────────────────────────────────────
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

# ── Configs: load + auto-create default ───────────────────────────────────────
configs = list_configs(user_email)
if not configs:
    create_config(user_email, "Default")
    configs = list_configs(user_email)

config_ids = [c["id"] for c in configs]
if st.session_state.get("active_config_id") not in config_ids:
    st.session_state["active_config_id"] = configs[0]["id"]

# Active config object
active_config = next(c for c in configs if c["id"] == st.session_state["active_config_id"])

# ── Configuration selector ────────────────────────────────────────────────────
st.markdown("---")
st.header("Configuration")
st.caption(
    "Each configuration is its own job tracker. Use a separate config for each search "
    "(e.g. *California*, *London*) — they keep their location, radius, optional resume "
    "override and job list separate."
)

cfg_a, cfg_b, cfg_c = st.columns([4, 1, 1])
with cfg_a:
    names = [c["name"] for c in configs]
    current_idx = names.index(active_config["name"])
    selected_name = st.selectbox(
        "Active configuration",
        names,
        index=current_idx,
        key="cfg_picker",
    )
    new_active = next(c for c in configs if c["name"] == selected_name)
    if new_active["id"] != active_config["id"]:
        st.session_state["active_config_id"] = new_active["id"]
        st.rerun()
with cfg_b:
    if st.button("➕ New", use_container_width=True):
        st.session_state["show_new_config"] = True
with cfg_c:
    if st.button("🗑 Delete", use_container_width=True,
                 disabled=len(configs) <= 1):
        st.session_state["show_delete_config"] = True

if st.session_state.get("show_new_config"):
    with st.form("new_config_form", clear_on_submit=True):
        new_name = st.text_input("Configuration name",
                                 placeholder="e.g. California Search, London Search")
        sub = st.form_submit_button("Create")
        cancel = st.form_submit_button("Cancel")
        if sub and new_name.strip():
            try:
                created = create_config(user_email, new_name.strip())
                st.session_state["active_config_id"] = created["id"]
                st.session_state.pop("show_new_config", None)
                st.rerun()
            except Exception as e:
                st.error(f"Could not create config: {e}")
        elif cancel:
            st.session_state.pop("show_new_config", None)
            st.rerun()

if st.session_state.get("show_delete_config"):
    st.warning(
        f"Delete configuration **{active_config['name']}** and **all its jobs**? "
        "This cannot be undone."
    )
    d_a, d_b = st.columns(2)
    if d_a.button("Yes, delete", type="primary"):
        delete_config(active_config["id"])
        st.session_state.pop("active_config_id", None)
        st.session_state.pop("show_delete_config", None)
        st.rerun()
    if d_b.button("Cancel"):
        st.session_state.pop("show_delete_config", None)
        st.rerun()

# ── Effective resume for the active config ───────────────────────────────────
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
    """Render the resume upload form. User picks save scope."""
    upload_col1, upload_col2 = st.columns(2)
    with upload_col1:
        resume_file = st.file_uploader(
            "Resume *",
            type=["pdf", "docx", "txt"],
            key="resume_uploader",
        )
    with upload_col2:
        cl_file = st.file_uploader(
            "Cover Letter (optional)",
            type=["pdf", "docx", "txt"],
            key="cl_uploader",
        )

    save_as_override = st.checkbox(
        f"Use this resume only for the **{active_config['name']}** configuration",
        value=False,
        help=("If unchecked, this becomes your main resume — used by every "
              "configuration that doesn't have its own override."),
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
                f"Could not save resume to the database: {e}. "
                "Check that the Supabase tables exist (run supabase_schema.sql)."
            )
            return

        st.session_state.pop("show_upload", None)
        scope = active_config["name"] if save_as_override else "all configs (main resume)"
        st.success(
            f"Saved! Found {len(profile['skills'])} skills, "
            f"{len(profile['titles'])} candidate titles. Scope: {scope}."
        )
        st.rerun()


st.markdown("---")

if has_effective_resume and not st.session_state.get("show_upload", False):
    st.header("Resume")

    if eff_source == "override":
        st.caption(f"Using a resume specific to **{active_config['name']}**.")
    else:
        st.caption("Using your main resume — shared by all configs without an override.")

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
                         help="Remove this config's override and fall back to your main resume."):
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


# ── Location Filter (just below the resume block) ─────────────────────────────
st.markdown("---")
st.header("Search Location")
st.caption(f"Settings for the **{active_config['name']}** configuration. "
           "Switch configs above to change context.")

cfg_loc = active_config.get("location")
cfg_radius_db = active_config.get("radius_miles")


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


# Reset widget state when the active config changes (so each config remembers
# its own location/radius without cross-talk).
if st.session_state.get("_loc_ctx_cfg_id") != active_config["id"]:
    st.session_state["loc_mode"] = _initial_mode(cfg_loc)
    st.session_state["loc_city"] = cfg_loc if cfg_loc in MAJOR_CITIES else MAJOR_CITIES[0]
    st.session_state["loc_state"] = cfg_loc if cfg_loc in US_STATES else "California"
    st.session_state["loc_custom"] = (
        cfg_loc if cfg_loc and cfg_loc not in MAJOR_CITIES + US_STATES + [REMOTE_LABEL]
        else ""
    )
    st.session_state["loc_radius"] = cfg_radius_db if cfg_radius_db is not None else 25
    st.session_state["_loc_ctx_cfg_id"] = active_config["id"]

mode_options = ["Major City", "State", "Remote", "Custom"]
mode = st.radio(
    "Location type",
    mode_options,
    horizontal=True,
    key="loc_mode",
)

selected_location: str | None = None
needs_radius = False

if mode == "Major City":
    selected_location = st.selectbox("City", MAJOR_CITIES, key="loc_city")
    needs_radius = True
elif mode == "State":
    selected_location = st.selectbox("State", US_STATES, key="loc_state")
elif mode == "Remote":
    selected_location = REMOTE_LABEL
    st.info("Searches will target remote roles in the United States.")
else:
    selected_location = st.text_input(
        "Custom location",
        placeholder="e.g. Boulder, CO or London, UK",
        key="loc_custom",
    )
    needs_radius = bool(selected_location)

if needs_radius:
    radius = st.slider(
        "Search radius (miles)",
        min_value=0, max_value=100, step=5,
        key="loc_radius",
        help="0 = exact city only. Higher values pull in surrounding areas.",
    )
else:
    radius = 0


# ── Job Search ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.header("Search for Jobs")

if not has_effective_resume:
    st.info("Upload a resume above to enable job search.")
elif not selected_location:
    st.info("Pick a location above to enable job search.")
else:
    # Compose the location string used in queries.
    if mode == "Remote":
        location_for_search = "Remote United States"
    elif radius and radius > 0 and mode in ("Major City", "Custom"):
        location_for_search = f"within {radius} miles of {selected_location}"
    else:
        location_for_search = selected_location

    live_queries = build_queries(eff_skills, eff_titles, [location_for_search])

    st.caption(
        f"Will run **{len(live_queries)}** searches targeting **{location_for_search}** "
        f"and save results into the **{active_config['name']}** tracker."
    )
    with st.expander("Preview queries", expanded=False):
        for q in live_queries:
            st.markdown(f"- {q}")

    if st.button("Search Jobs Now", type="primary", use_container_width=True):
        from utils.job_search import search_jobs
        from utils.db import insert_job, is_duplicate

        # Persist the location/radius onto the active config.
        try:
            update_config(active_config["id"], {
                "location": selected_location,
                "radius_miles": radius if radius > 0 else None,
            })
        except Exception:
            pass

        if not live_queries:
            st.error("Couldn't build any queries — re-upload your resume so we can detect skills/titles.")
            st.stop()

        status_box = st.empty()
        status_box.info(f"Starting search for **{active_config['name']}**...")

        jobs = search_jobs(
            queries=live_queries,
            user_skills=eff_skills,
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
            status_box.info(
                f"Found {len(jobs)} jobs. Saving new ones into **{active_config['name']}**..."
            )
            added = skipped = failed = 0
            last_error = ""
            progress = st.progress(0)

            for i, job in enumerate(jobs):
                progress.progress((i + 1) / len(jobs))
                try:
                    if is_duplicate(
                        job["company"], job["job_title"],
                        user_email=user_email,
                        config_id=active_config["id"],
                    ):
                        skipped += 1
                        continue
                    job["config_id"] = active_config["id"]
                    insert_job(job)
                    added += 1
                except Exception as e:
                    failed += 1
                    last_error = f"{type(e).__name__}: {str(e)[:160]}"

            progress.empty()

            if added > 0:
                status_box.success(
                    f"Done! Added **{added}** new jobs to **{active_config['name']}**. "
                    f"({skipped} duplicates skipped, {failed} failed.) "
                    "Open the **Job Board** in the sidebar to manage them."
                )
            else:
                status_box.error(
                    f"Search ran but nothing was saved. "
                    f"{skipped} were duplicates, {failed} failed to insert. "
                    + (f"Last error: {last_error}" if last_error else
                       "Check that the Supabase schema is up to date "
                       "(run supabase_schema.sql).")
                )

st.markdown("---")
st.markdown(
    """
    ### Pages
    - **Dashboard** — Stats & charts overview
    - **Job Board** — Tracker diary scoped to your active config (or all)
    """
)
st.caption("Built with Streamlit + Supabase")
