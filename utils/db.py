"""All Supabase read/write functions."""

import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


@st.cache_data(ttl=30)
def load_jobs(active_only: bool = True) -> pd.DataFrame:
    client = get_client()
    query = client.table("jobs").select("*").order("id")
    if active_only:
        query = query.eq("is_active", True)
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


def is_duplicate(company: str, job_title: str) -> bool:
    df = load_jobs(active_only=False)
    if df.empty:
        return False
    mask = (
        df["company"].str.lower().str.strip() == company.lower().strip()
    ) & (
        df["job_title"].str.lower().str.strip() == job_title.lower().strip()
    )
    return bool(mask.any())
