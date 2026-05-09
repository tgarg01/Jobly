"""Search for jobs across multiple boards using DuckDuckGo."""

import re
import time
import hashlib
from datetime import date
from urllib.parse import urlparse

from ddgs import DDGS


# ── Domain filtering ─────────────────────────────────────────────────────────
# We restrict every query to job-board domains via `site:` so DuckDuckGo
# doesn't return YouTube videos, blog posts, news articles, etc.

# Domains we accept results from. Suffix match — "linkedin.com" also
# matches "uk.linkedin.com".
ALLOWED_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "simplyhired.com",
    "lever.co",
    "greenhouse.io",
    "workday.com",
    "myworkdayjobs.com",
    "wellfound.com",
    "builtin.com",
    "dice.com",
    "remoteok.com",
    "remoteok.io",
    "weworkremotely.com",
    "themuse.com",
    "icims.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "recruitee.com",
    "bamboohr.com",
    "biospace.com",
    "naturejobs.com",
    "sciencecareers.org",
)

# Domains we never want even if a stray result slips through.
BLOCKED_DOMAINS = (
    "youtube.com", "youtu.be",
    "facebook.com", "twitter.com", "x.com",
    "reddit.com", "instagram.com", "tiktok.com",
    "medium.com", "wikipedia.org", "wikia.com",
    "quora.com", "blogspot.com", "tumblr.com",
    "amazon.com", "ebay.com", "pinterest.com",
    "stackoverflow.com",
    "github.com",
)

# Site-OR filter prepended to every query. Limited list for compatibility —
# very long OR chains have caused empty result sets in DDGS.
_SEARCH_BOARDS = (
    "linkedin.com/jobs",
    "indeed.com",
    "glassdoor.com",
    "lever.co",
    "greenhouse.io",
    "ziprecruiter.com",
)
_SITE_OR_FILTER = "(" + " OR ".join(f"site:{b}" for b in _SEARCH_BOARDS) + ")"


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _is_allowed_url(url: str) -> bool:
    if not url:
        return False
    host = _host(url)
    if not host:
        return False

    for bad in BLOCKED_DOMAINS:
        if host == bad or host.endswith("." + bad):
            return False

    url_lower = url.lower()
    # Reject search results / category listing pages — only want specific postings.
    if any(s in url_lower for s in (
        "/search?", "?q=", "?query=", "/serp", "/results?",
        "/jobs/search", "/jobs?", "/companies/",
    )):
        return False

    for good in ALLOWED_DOMAINS:
        if host == good or host.endswith("." + good):
            return True

    # Otherwise, accept only if the URL strongly looks like a job-posting page
    # (e.g. company career pages with /careers/job/123).
    job_path_signals = (
        "/job/", "/jobs/", "/career/", "/careers/", "/opening/",
        "/openings/", "/position/", "/positions/", "/vacancy/", "/req/",
    )
    return any(p in url_lower for p in job_path_signals)


# ── Field extraction ─────────────────────────────────────────────────────────

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
    host = _host(url)
    aggregator_labels = {
        "linkedin.com": "LinkedIn listing",
        "indeed.com": "Indeed listing",
        "glassdoor.com": "Glassdoor listing",
        "ziprecruiter.com": "ZipRecruiter listing",
        "monster.com": "Monster listing",
        "simplyhired.com": "SimplyHired listing",
        "biospace.com": "BioSpace listing",
    }
    for domain, label in aggregator_labels.items():
        if domain in host:
            return label
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return host or "Unknown"


def _extract_company(title: str, body: str, url: str) -> str:
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
        r"\s*[\|–—-]\s*Greenhouse.*$",
        r"\s*[\|–—-]\s*Lever.*$",
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


def _dedup_key(company: str, job_title: str) -> str:
    """Dedup on (company, title) only — same posting cross-listed on LinkedIn
    + Indeed + Glassdoor should collapse to one row."""
    raw = f"{company.lower().strip()}|{job_title.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


_GARBAGE_TITLES = {"jobs", "search", "careers", "home", ""}


def _parse_result(r: dict, user_skills: list[str],
                  seen_keys: set, seen_urls: set) -> dict | None:
    url = r.get("href", "") or r.get("link", "")
    title = r.get("title", "")
    body = r.get("body", "") or r.get("snippet", "")

    if not url or not title:
        return None
    if not _is_allowed_url(url):
        return None
    if url in seen_urls:
        return None
    seen_urls.add(url)

    job_title = _extract_job_title(title)
    company = _extract_company(title, body, url)

    if not job_title or job_title.lower().strip() in _GARBAGE_TITLES:
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


def search_jobs(queries: list[str], user_skills: list[str],
                max_results_per_query: int = 10,
                status_container=None, user_email: str = None) -> list[dict]:
    """Search DuckDuckGo for jobs across multiple queries.

    Each query is wrapped in a `site:` OR filter so DDG only returns from
    job boards (LinkedIn / Indeed / Glassdoor / Lever / Greenhouse /
    ZipRecruiter). Result URLs are also re-checked against an allow-list /
    block-list to drop anything that slips through (YouTube, Reddit, blogs).
    """
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []
    errors: list[str] = []
    total_results = 0
    rejected_url = 0

    base_queries = queries[:8]
    queries_to_run = [f"{_SITE_OR_FILTER} {q}" for q in base_queries]

    ddgs = DDGS()
    for i, q in enumerate(queries_to_run):
        base_q = base_queries[i]
        if status_container:
            status_container.info(
                f"Searching ({i+1}/{len(queries_to_run)}): {base_q[:60]}...  "
                f"[{len(all_jobs)} jobs found so far]"
            )
        try:
            results = list(ddgs.text(q, max_results=max_results_per_query, region="us-en"))
            total_results += len(results)
            for r in results:
                # Track URL rejections for diagnostics.
                url = r.get("href") or r.get("link", "")
                if url and not _is_allowed_url(url):
                    rejected_url += 1
                    continue
                job = _parse_result(r, user_skills, seen_keys, seen_urls)
                if job:
                    if user_email:
                        job["user_email"] = user_email
                    all_jobs.append(job)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:100]}"
            errors.append(f"Query '{base_q[:40]}': {error_msg}")
            if status_container:
                status_container.warning(f"Search issue on query {i+1}: {error_msg}")
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
                f"Got {total_results} raw results → {len(all_jobs)} unique jobs "
                f"({rejected_url} non-job URLs filtered out). "
                f"First error: {errors[0]}"
            )
        else:
            status_container.success(
                f"Search complete! {total_results} raw results → "
                f"{len(all_jobs)} unique jobs "
                f"({rejected_url} non-job URLs filtered out)."
            )

    all_jobs.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
    return all_jobs
