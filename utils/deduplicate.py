"""Duplicate detection utilities."""

from utils.db import is_duplicate


def check_duplicate(company: str, job_title: str) -> bool:
    """Return True if a job with the same company + title already exists."""
    return is_duplicate(company, job_title)
