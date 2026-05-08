"""Extract text and key skills from uploaded resume/cover letter files."""

import re
from io import BytesIO

# ── Known skill keywords for cancer biology / oncology ──────────────────────────
SKILL_KEYWORDS = [
    "CRISPR", "scRNA-seq", "RNA-seq", "single-cell", "flow cytometry",
    "immunohistochemistry", "IHC", "Western blot", "qPCR", "RT-PCR",
    "cell culture", "mouse models", "in vivo", "in vitro", "tumor microenvironment",
    "oncology", "cancer biology", "immunology", "immuno-oncology",
    "bioinformatics", "genomics", "proteomics", "metabolomics",
    "next-generation sequencing", "NGS", "whole exome sequencing",
    "ChIP-seq", "ATAC-seq", "epigenetics", "gene editing",
    "molecular biology", "biochemistry", "cell signaling",
    "drug discovery", "clinical trials", "GLP", "GMP",
    "Python", "R", "MATLAB", "statistical analysis", "machine learning",
    "data analysis", "scientific writing", "grant writing",
    "confocal microscopy", "fluorescence microscopy", "FACS",
    "protein purification", "cloning", "transfection",
    "ELISA", "mass spectrometry", "LC-MS", "NMR",
    "stem cells", "organoids", "3D cell culture",
    "CAR-T", "checkpoint inhibitors", "immunotherapy",
    "pharmacology", "toxicology", "pathology",
    "biomarkers", "liquid biopsy", "ctDNA",
    "GMP manufacturing", "process development",
    "regulatory affairs", "FDA", "IND",
    "postdoc", "postdoctoral", "research scientist", "research associate",
    "principal investigator", "PI", "lab manager",
]

# ── Common job title patterns ──────────────────────────────────────────────────
JOB_TITLE_PATTERNS = [
    r"postdoc(?:toral)?\s+(?:fellow|researcher|scientist|position)",
    r"research\s+(?:scientist|associate|fellow|analyst)",
    r"senior\s+(?:scientist|researcher|associate)",
    r"(?:staff|principal)\s+scientist",
    r"lab(?:oratory)?\s+(?:manager|director|technician)",
    r"bioinformatics\s+(?:scientist|analyst|engineer)",
    r"clinical\s+(?:scientist|researcher|trial)",
    r"(?:medical|scientific)\s+(?:director|advisor|liaison)",
]


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(pages)
    except Exception:
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF or DOCX based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    return ""


def extract_skills(text: str) -> list[str]:
    """Find known skills mentioned in the text."""
    text_lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        if skill.lower() in text_lower:
            found.append(skill)
    return sorted(set(found))


def extract_job_titles(text: str) -> list[str]:
    """Find likely job title patterns in the text."""
    found = []
    text_lower = text.lower()
    for pattern in JOB_TITLE_PATTERNS:
        matches = re.findall(pattern, text_lower)
        found.extend(matches)
    return sorted(set(found))


def extract_location_preferences(text: str) -> list[str]:
    """Find location mentions in the text."""
    locations = []
    location_patterns = [
        r"(?:Bay Area|San Francisco|South San Francisco|San Jose|Palo Alto|"
        r"Mountain View|Sunnyvale|Santa Clara|Redwood City|Emeryville|"
        r"Berkeley|Oakland|Foster City|San Mateo|Fremont|Hayward|"
        r"San Diego|Los Angeles|Sacramento|California|CA)",
    ]
    for pattern in location_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        locations.extend(matches)
    if not locations:
        locations = ["Bay Area, CA"]
    return sorted(set(locations))


def build_search_profile(resume_text: str, cover_letter_text: str = "") -> dict:
    """Build a search profile from resume and cover letter text."""
    combined = f"{resume_text}\n{cover_letter_text}"
    skills = extract_skills(combined)
    titles = extract_job_titles(combined)
    locations = extract_location_preferences(combined)

    # Build search queries from the profile
    queries = []

    # Skill-based queries
    top_skills = skills[:5] if skills else ["cancer biology", "oncology"]
    skill_str = " ".join(top_skills[:3])
    for loc in locations[:2]:
        queries.append(f"{skill_str} jobs {loc}")
        queries.append(f"postdoc {skill_str} {loc}")
        queries.append(f"research scientist {skill_str} {loc}")

    # Title-based queries
    for title in titles[:3]:
        for loc in locations[:2]:
            queries.append(f"{title} jobs {loc}")

    # Broad queries
    queries.append("cancer biology postdoc jobs California")
    queries.append("oncology research scientist jobs Bay Area")
    queries.append("biotech research jobs San Francisco Bay Area")
    queries.append("immuno-oncology jobs California")
    queries.append("bioinformatics cancer research jobs Bay Area")

    return {
        "skills": skills,
        "titles": titles,
        "locations": locations,
        "queries": list(dict.fromkeys(queries)),  # deduplicate, preserve order
    }
