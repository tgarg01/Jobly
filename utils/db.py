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
    """Fetch a user profile by email. Returns None if not found."""
    client = get_client()
    result = client.table("user_profiles").select("*").eq("email", email).execute()
    if result.data:
        return result.data[0]
    return None


def save_user_profile(email: str, resume_text: str, cover_letter_text: str,
                      resume_filename: str, cover_letter_filename: str,
                      skills: list[str], search_queries: list[str]):
    """Create or update a user profile."""
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
        "updated_at": str(date.today()),
    }

    if existing:
        client.table("user_profiles").update(profile_data).eq("email", email).execute()
    else:
        profile_data["created_at"] = str(date.today())
        client.table("user_profiles").insert(profile_data).execute()


def delete_user_resume(email: str):
    """Clear resume and cover letter data for a user."""
    client = get_client()
    client.table("user_profiles").update({
        "resume_text": None,
        "cover_letter_text": None,
        "resume_filename": None,
        "cover_letter_filename": None,
        "skills": None,
        "search_queries": None,
        "updated_at": str(date.today()),
    }).eq("email", email).execute()


# ── Jobs ───────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_jobs(active_only: bool = True, user_email: str = None) -> pd.DataFrame:
    client = get_client()
    query = client.table("jobs").select("*").order("id", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    if user_email:
        query = query.eq("user_email", user_email)
    result = query.execute()
    return pd.DataFrame(result.data)


def insert_job(row: dict) -> dict:
    """Insert a new job. Returns the inserted row or raises on duplicate."""
    client = get_client()
    result = client.table("jobs").insert(row).execute()
    load_jobs.clear()
    return result.data[0] if result.data else {}


def update_job(job_id: int, fields: dict):
    """Update any fields on a job row by id."""
    client = get_client()
    client.table("jobs").update(fields).eq("id", job_id).execute()
    load_jobs.clear()


def mark_applied(job_id: int):
    update_job(job_id, {"applied_date": str(date.today())})


def hide_job(job_id: int):
    update_job(job_id, {"is_active": False})


def is_duplicate(company: str, job_title: str, user_email: str = None) -> bool:
    df = load_jobs(active_only=False, user_email=user_email)
    if df.empty:
        return False
    mask = (
        df["company"].str.lower().str.strip() == company.lower().strip()
    ) & (
        df["job_title"].str.lower().str.strip() == job_title.lower().strip()
    )
    return bool(mask.any())
