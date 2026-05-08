"""All Supabase read/write functions."""

import json
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


# ── User Profiles ──────────────────────────────────────────────────────────────

def get_user_profile(email: str) -> dict | None:
    client = get_client()
    result = client.table("user_profiles").select("*").eq("email", email).execute()
    if result.data:
        return result.data[0]
    return None


def save_user_profile(email: str, resume_text: str, cover_letter_text: str,
                      resume_filename: str, cover_letter_filename: str,
                      skills: list[str], search_queries: list[str],
                      titles: list[str] | None = None,
                      preferred_location: str | None = None):
    client = get_client()
    existing = get_user_profile(email)

    profile_data = {
        "email": email,
        "resume_text": resume_text,
        "cover_letter_text": cover_letter_text or None,
        "resume_filename": resume_filename,
        "cover_letter_filename": cover_letter_filename or None,
        "skills": json.dumps(skills),
        "search_queries": json.dumps(search_queries),
        "titles": json.dumps(titles or []),
        "preferred_location": preferred_location,
        "updated_at": str(date.today()),
    }

    if existing:
        client.table("user_profiles").update(profile_data).eq("email", email).execute()
    else:
        profile_data["created_at"] = str(date.today())
        client.table("user_profiles").insert(profile_data).execute()


def save_preferred_location(email: str, location: str):
    client = get_client()
    client.table("user_profiles").update({
        "preferred_location": location,
        "updated_at": str(date.today()),
    }).eq("email", email).execute()


def delete_user_resume(email: str):
    client = get_client()
    client.table("user_profiles").update({
        "resume_text": None,
        "cover_letter_text": None,
        "resume_filename": None,
        "cover_letter_filename": None,
        "skills": None,
        "search_queries": None,
        "titles": None,
        "updated_at": str(date.today()),
    }).eq("email", email).execute()


# ── Configs ────────────────────────────────────────────────────────────────────

def list_configs(user_email: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("configs").select("*")
        .eq("user_email", user_email)
        .order("id")
        .execute()
    )
    return result.data or []


def get_config(config_id: int) -> dict | None:
    client = get_client()
    result = client.table("configs").select("*").eq("id", config_id).execute()
    return result.data[0] if result.data else None


def create_config(user_email: str, name: str,
                  location: str | None = None,
                  radius_miles: int | None = None) -> dict:
    client = get_client()
    data = {
        "user_email": user_email,
        "name": name,
        "location": location,
        "radius_miles": radius_miles,
    }
    result = client.table("configs").insert(data).execute()
    return result.data[0] if result.data else {}


def update_config(config_id: int, fields: dict):
    client = get_client()
    fields = {**fields, "updated_at": str(date.today())}
    client.table("configs").update(fields).eq("id", config_id).execute()
    load_jobs.clear()


def clear_config_resume_override(config_id: int):
    update_config(config_id, {
        "override_resume_text": None,
        "override_cover_letter_text": None,
        "override_resume_filename": None,
        "override_cover_letter_filename": None,
        "override_skills": None,
        "override_titles": None,
    })


def delete_config(config_id: int):
    """Delete a config and all its jobs."""
    client = get_client()
    client.table("jobs").delete().eq("config_id", config_id).execute()
    client.table("configs").delete().eq("id", config_id).execute()
    load_jobs.clear()


# ── Jobs ───────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_jobs(active_only: bool = True, user_email: str = None,
              config_id: int | None = None) -> pd.DataFrame:
    client = get_client()
    query = client.table("jobs").select("*").order("id", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    if user_email:
        query = query.eq("user_email", user_email)
    if config_id is not None:
        query = query.eq("config_id", config_id)
    result = query.execute()
    return pd.DataFrame(result.data)


def insert_job(row: dict) -> dict:
    client = get_client()
    result = client.table("jobs").insert(row).execute()
    load_jobs.clear()
    return result.data[0] if result.data else {}


def update_job(job_id: int, fields: dict):
    client = get_client()
    client.table("jobs").update(fields).eq("id", job_id).execute()
    load_jobs.clear()


def mark_applied(job_id: int):
    update_job(job_id, {
        "applied_date": str(date.today()),
        "status": "waiting",
    })


def set_job_status(job_id: int, status: str | None):
    update_job(job_id, {"status": status})


def hide_job(job_id: int):
    update_job(job_id, {"is_active": False})


def is_duplicate(company: str, job_title: str, user_email: str = None,
                 config_id: int | None = None) -> bool:
    df = load_jobs(active_only=False, user_email=user_email, config_id=config_id)
    if df.empty:
        return False
    mask = (
        df["company"].str.lower().str.strip() == company.lower().strip()
    ) & (
        df["job_title"].str.lower().str.strip() == job_title.lower().strip()
    )
    return bool(mask.any())
