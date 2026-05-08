"""Constants used across the Jobly app."""

JOB_TYPES = ["Postdoc", "Industry"]

DEFAULT_LOCATION = "Bay Area, CA"

COLUMN_ORDER = [
    "id",
    "company",
    "job_title",
    "location",
    "job_link",
    "posted_date",
    "applied_date",
    "contact_info",
    "job_type",
    "key_skills",
    "comments",
    "fit_score",
    "salary",
    "added_on",
    "is_active",
]

DISPLAY_COLUMNS = [
    "company",
    "job_title",
    "location",
    "job_type",
    "fit_score",
    "applied_date",
    "salary",
    "comments",
]

FLAG_KEYWORDS = [
    "link not working",
    "no longer exists",
    "irrelevant",
    "expired",
    "closed",
    "removed",
]
