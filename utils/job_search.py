"""Search for jobs across multiple boards using DuckDuckGo."""

import re
import time
import hashlib
from datetime import date
from urllib.parse import urlparse

from ddgs import DDGS


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _guess_job_type(text: str) -> str:
    lower = text.lower()
    postdoc_keywords = ["postdoc", "postdoctoral", "fellow", "fellowship",
                        "principal investigator", " pi "]
    if any(kw in lower for kw in postdoc_keywords):
        return "Postdoc"
    return "Industry"


def _company_from_url(url: str) -> str:
    """Best-effort company name from the URL host (used when we can't parse the title)."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    host = host.replace("www.", "")

    aggregator_labels = {
        "linkedin.com": "LinkedIn listing",
        "indeed.com": "Indeed listing",
        "glassdoor.com": "Glassdoor listing",
        "ziprecruiter.com": "ZipRecruiter listing",
        "monster.com": "Monster listing",
        "simplyhired.com": "SimplyHired listing",
        "google.com": "Google Jobs",
        "biospace.com": "BioSpace listing",
        "nature.com": "Nature Careers",
        "sciencecareers.org": "Science Careers",
    }
    for domain, label in aggregator_labels.items():
        if domain in host:
            return label

    # Fall back to second-level domain (e.g. "genentech.com" -> "Genentech")
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return host or "Unknown"


def _extract_company(title: str, body: str, url: str) -> str:
    """Try to extract company name from search result, falling back to the URL."""
    for sep in [" at ", " - ", " | ", " — ", " – "]:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                for suffix in [" | LinkedIn", " | Indeed", " | Glassdoor",
                               " Jobs", " Careers", " - LinkedIn"]:
                    candidate = candidate.replace(suffix, "").strip()
                if candidate and 1 < len(candidate) < 80:
                    return candidate

    return _company_from_url(url)


def _extract_job_title(title: str) -> str:
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
        r"Remote",
        r"California",
    ]
    for pattern in bay_area_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_salary(body: str) -> str:
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
    body_lower = body.lower()
    found = [s for s in known_skills if s.lower() in body_lower]
    return ", ".join(found[:8]) if found else ""


def _compute_fit_score(job_text: str, user_skills: list[str]) -> int:
    if not user_skills:
        return 50
    job_lower = job_text.lower()
    matches = sum(1 for s in user_skills if s.lower() in job_lower)
    score = min(100, int((matches / max(len(user_skills), 1)) * 100))
    return max(10, score)


def _dedup_key(company: str, job_title: str, url: str) -> str:
    """Dedup on company+title, but include URL host so generic 'LinkedIn listing'
    rows for different jobs don't collapse into one."""
    host = ""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        pass
    raw = f"{company.lower().strip()}|{job_title.lower().strip()}|{host}"
    return hashlib.md5(raw.encode()).hexdigest()


_GARBAGE_TITLES = {"jobs", "search", "careers", "home", ""}


def _parse_result(r: dict, user_skills: list[str], seen_keys: set, seen_urls: set) -> dict | None:
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

    if not job_title or job_title.lower().strip() in _GARBAGE_TITLES:
        return None

    dk = _dedup_key(company, job_title, url)
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
                status_container=None, user_email: str = None) -> list[dict]:
    """Search DuckDuckGo for jobs across multiple queries.

    Returns a list of job dicts ready for Supabase insertion.
    """
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []
    errors: list[str] = []
    total_results = 0

    queries_to_run = queries[:8]
    total_queries = len(queries_to_run)

    ddgs = DDGS()

    for i, query in enumerate(queries_to_run):
        if status_container:
            status_container.info(
                f"Searching ({i+1}/{total_queries}): {query[:60]}...  "
                f"[{len(all_jobs)} jobs found so far]"
            )

        try:
            results = list(ddgs.text(
                query,
                max_results=max_results_per_query,
                region="us-en",
            ))
            total_results += len(results)

            for r in results:
                job = _parse_result(r, user_skills, seen_keys, seen_urls)
                if job:
                    if user_email:
                        job["user_email"] = user_email
                    all_jobs.append(job)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:100]}"
            errors.append(f"Query '{query[:40]}': {error_msg}")
            if status_container:
                status_container.warning(f"Search issue on query {i+1}: {error_msg}")

        # Delay between queries to avoid rate limiting
        time.sleep(1.5)

    if status_container:
        if errors and not all_jobs:
            status_container.error(
                f"All {len(errors)} queries failed (likely rate-limited). "
                f"Wait a minute and retry. First error: {errors[0]}"
            )
        elif errors:
            status_container.warning(
                f"Completed with {len(errors)} issues. "
                f"Got {total_results} raw results → {len(all_jobs)} unique jobs. "
                f"First error: {errors[0]}"
            )
        else:
            status_container.success(
                f"Search complete! {total_results} raw results → {len(all_jobs)} unique jobs."
            )

    all_jobs.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
    return all_jobs
