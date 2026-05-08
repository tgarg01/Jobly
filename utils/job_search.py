"""Search for jobs across multiple boards using DuckDuckGo."""

import re
import time
import hashlib
import streamlit as st
from datetime import date
from ddgs import DDGS


def _clean_text(text: str) -> str:
    """Remove extra whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _guess_job_type(text: str) -> str:
    """Guess if a job is Postdoc or Industry."""
    lower = text.lower()
    postdoc_keywords = ["postdoc", "postdoctoral", "fellow", "fellowship", "PI ", "principal investigator"]
    if any(kw in lower for kw in postdoc_keywords):
        return "Postdoc"
    return "Industry"


def _extract_company(title: str, body: str, url: str) -> str:
    """Try to extract company name from search result."""
    for sep in [" at ", " - ", " | ", " — ", " – "]:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                for suffix in [" | LinkedIn", " | Indeed", " | Glassdoor", " Jobs", " Careers"]:
                    candidate = candidate.replace(suffix, "").strip()
                if candidate and len(candidate) < 80:
                    return candidate

    if "linkedin.com" in url:
        return _clean_text(title.split("-")[-1].strip() if "-" in title else "Unknown")
    if "indeed.com" in url or "glassdoor.com" in url:
        return _clean_text(title.split("-")[-1].strip() if "-" in title else "Unknown")

    return "Unknown"


def _extract_job_title(title: str) -> str:
    """Extract the actual job title from the search result title."""
    for suffix_pattern in [
        r"\s*[\|–—-]\s*LinkedIn.*$",
        r"\s*[\|–—-]\s*Indeed.*$",
        r"\s*[\|–—-]\s*Glassdoor.*$",
        r"\s*[\|–—-]\s*ZipRecruiter.*$",
        r"\s*[\|–—-]\s*Google.*$",
        r"\s*[\|–—-]\s*Salary\.com.*$",
        r"\s*[\|–—-]\s*BioSpace.*$",
    ]:
        title = re.sub(suffix_pattern, "", title, flags=re.IGNORECASE)

    for sep in [" at ", " - ", " | ", " — ", " – "]:
        if sep in title:
            return _clean_text(title.split(sep)[0])

    return _clean_text(title)


def _extract_location(body: str) -> str:
    """Try to extract location from the result body."""
    bay_area_patterns = [
        r"South San Francisco(?:,\s*CA)?",
        r"San Francisco(?:,\s*CA)?",
        r"Palo Alto(?:,\s*CA)?",
        r"Mountain View(?:,\s*CA)?",
        r"Sunnyvale(?:,\s*CA)?",
        r"Santa Clara(?:,\s*CA)?",
        r"San Jose(?:,\s*CA)?",
        r"Redwood City(?:,\s*CA)?",
        r"Emeryville(?:,\s*CA)?",
        r"Berkeley(?:,\s*CA)?",
        r"Oakland(?:,\s*CA)?",
        r"Foster City(?:,\s*CA)?",
        r"San Mateo(?:,\s*CA)?",
        r"Fremont(?:,\s*CA)?",
        r"San Diego(?:,\s*CA)?",
        r"Los Angeles(?:,\s*CA)?",
        r"Sacramento(?:,\s*CA)?",
        r"Bay Area(?:,\s*CA)?",
        r"California",
    ]
    for pattern in bay_area_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_salary(body: str) -> str:
    """Try to extract salary from the result body."""
    salary_patterns = [
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:per\s+)?(?:year|yr|annually|/yr|/year))?",
        r"[\d,]+k\s*[-–]\s*[\d,]+k",
    ]
    for pattern in salary_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_skills_from_body(body: str, known_skills: list[str]) -> str:
    """Find known skills mentioned in the job description body."""
    body_lower = body.lower()
    found = [s for s in known_skills if s.lower() in body_lower]
    return ", ".join(found[:8]) if found else ""


def _compute_fit_score(job_text: str, user_skills: list[str]) -> int:
    """Compute a simple fit score based on skill overlap."""
    if not user_skills:
        return 50
    job_lower = job_text.lower()
    matches = sum(1 for s in user_skills if s.lower() in job_lower)
    score = min(100, int((matches / max(len(user_skills), 1)) * 100))
    return max(10, score)


def _dedup_key(company: str, job_title: str) -> str:
    """Generate a deduplication key."""
    raw = f"{company.lower().strip()}|{job_title.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _parse_result(r: dict, user_skills: list[str], seen_keys: set, seen_urls: set) -> dict | None:
    """Parse a single search result into a job dict, or None if invalid/duplicate."""
    url = r.get("href", "") or r.get("link", "")
    title = r.get("title", "")
    body = r.get("body", "") or r.get("snippet", "")

    if not url or not title:
        return None

    if url in seen_urls:
        return None
    seen_urls.add(url)

    job_title = _extract_job_title(title)
    company = _extract_company(title, body, url)

    if not job_title or job_title.lower() in ["jobs", "search", "careers", ""]:
        return None

    dk = _dedup_key(company, job_title)
    if dk in seen_keys:
        return None
    seen_keys.add(dk)

    combined_text = f"{title} {body}"
    location = _extract_location(combined_text)
    salary = _extract_salary(combined_text)
    skills = _extract_skills_from_body(combined_text, user_skills)
    fit_score = _compute_fit_score(combined_text, user_skills)
    job_type = _guess_job_type(combined_text)

    return {
        "company": company[:200],
        "job_title": job_title[:200],
        "location": location or None,
        "job_link": url,
        "posted_date": str(date.today()),
        "job_type": job_type,
        "key_skills": skills or None,
        "fit_score": fit_score,
        "salary": salary or None,
        "is_active": True,
    }


def search_jobs(queries: list[str], user_skills: list[str], max_results_per_query: int = 10,
                status_container=None) -> list[dict]:
    """
    Search DuckDuckGo for jobs across multiple queries.
    Returns a list of job dicts ready for Supabase insertion.
    """
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []
    errors: list[str] = []

    total_queries = len(queries)

    for i, query in enumerate(queries):
        if status_container:
            status_container.text(f"Searching ({i+1}/{total_queries}): {query[:60]}...")

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results_per_query,
                    region="us-en",
                ))

            for r in results:
                job = _parse_result(r, user_skills, seen_keys, seen_urls)
                if job:
                    all_jobs.append(job)

        except Exception as e:
            errors.append(f"Query '{query[:40]}': {str(e)[:80]}")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    # Log errors for debugging
    if errors and status_container:
        status_container.warning(
            f"Some searches had issues ({len(errors)} of {total_queries}). "
            f"First error: {errors[0]}"
        )

    # Sort by fit score descending
    all_jobs.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
    return all_jobs
