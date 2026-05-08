"""Search for jobs across multiple boards using DuckDuckGo."""

import re
import hashlib
from datetime import date
from duckduckgo_search import DDGS


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
    # Common patterns in job listing titles: "Job Title at Company" or "Job Title - Company"
    for sep in [" at ", " - ", " | ", " — ", " – "]:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                # Remove common suffixes
                for suffix in [" | LinkedIn", " | Indeed", " | Glassdoor", " Jobs", " Careers"]:
                    candidate = candidate.replace(suffix, "").strip()
                if candidate and len(candidate) < 80:
                    return candidate

    # Try to get from URL domain
    if "linkedin.com" in url:
        return _clean_text(title.split("-")[-1].strip() if "-" in title else "Unknown")
    if "indeed.com" in url or "glassdoor.com" in url:
        return _clean_text(title.split("-")[-1].strip() if "-" in title else "Unknown")

    return "Unknown"


def _extract_job_title(title: str) -> str:
    """Extract the actual job title from the search result title."""
    # Remove common suffixes like "| LinkedIn", "- Indeed.com"
    for suffix_pattern in [
        r"\s*[\|–—-]\s*LinkedIn.*$",
        r"\s*[\|–—-]\s*Indeed.*$",
        r"\s*[\|–—-]\s*Glassdoor.*$",
        r"\s*[\|–—-]\s*ZipRecruiter.*$",
        r"\s*[\|–—-]\s*Google.*$",
    ]:
        title = re.sub(suffix_pattern, "", title, flags=re.IGNORECASE)

    # Split on common separators and take first part as job title
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
    return max(10, score)  # minimum 10


def _dedup_key(company: str, job_title: str) -> str:
    """Generate a deduplication key."""
    raw = f"{company.lower().strip()}|{job_title.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def search_jobs(queries: list[str], user_skills: list[str], max_results_per_query: int = 15) -> list[dict]:
    """
    Search DuckDuckGo for jobs across multiple queries.
    Returns a list of job dicts ready for Supabase insertion.
    """
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []

    # Target job board sites for better results
    site_prefixes = [
        "",  # general search
        "site:linkedin.com/jobs ",
        "site:indeed.com ",
        "site:glassdoor.com ",
    ]

    with DDGS() as ddgs:
        for query in queries:
            for site_prefix in site_prefixes:
                full_query = f"{site_prefix}{query}"
                try:
                    results = list(ddgs.text(
                        full_query,
                        max_results=max_results_per_query,
                    ))
                except Exception:
                    continue

                for r in results:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    body = r.get("body", "")

                    # Skip non-job URLs
                    if not url or not title:
                        continue

                    # Skip duplicate URLs
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    job_title = _extract_job_title(title)
                    company = _extract_company(title, body, url)

                    # Skip if we can't identify the job
                    if not job_title or job_title.lower() in ["jobs", "search", "careers"]:
                        continue

                    # Skip duplicates by company+title
                    dk = _dedup_key(company, job_title)
                    if dk in seen_keys:
                        continue
                    seen_keys.add(dk)

                    combined_text = f"{title} {body}"
                    location = _extract_location(combined_text)
                    salary = _extract_salary(combined_text)
                    skills = _extract_skills_from_body(combined_text, user_skills)
                    fit_score = _compute_fit_score(combined_text, user_skills)
                    job_type = _guess_job_type(combined_text)

                    job = {
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
                    all_jobs.append(job)

    # Sort by fit score descending
    all_jobs.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
    return all_jobs
