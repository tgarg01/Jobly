"""Extract text and key skills from uploaded resume/cover letter files."""

import re
from io import BytesIO


# ── Skill keywords across multiple domains ───────────────────────────────────
# Order doesn't drive priority — extract_skills() sorts hits by first
# appearance in the resume — but grouping keeps this list maintainable.
SKILL_KEYWORDS = [
    # === Programming languages ===
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Golang",
    "Rust", "Ruby", "Swift", "Kotlin", "PHP", "Scala", "R", "MATLAB", "Julia",
    "Perl", "Bash", "Shell", "PowerShell", "Lua", "Haskell", "Clojure",
    "Erlang", "Objective-C", "Dart", "Solidity",

    # === Web / frontend ===
    "React", "Angular", "Vue", "Vue.js", "Next.js", "Svelte", "jQuery",
    "HTML", "HTML5", "CSS", "CSS3", "SASS", "Tailwind", "Bootstrap",
    "Redux", "GraphQL", "Webpack", "Vite",

    # === Backend frameworks ===
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Rails",
    "Express", "Express.js", "Node.js", "ASP.NET", ".NET", "Laravel",
    "Symfony",

    # === Mobile ===
    "iOS", "Android", "React Native", "Flutter", "SwiftUI",
    "Jetpack Compose", "Xamarin",

    # === Databases ===
    "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra",
    "DynamoDB", "Elasticsearch", "Snowflake", "BigQuery", "Redshift",
    "Athena", "Oracle", "MariaDB", "Neo4j", "Firebase", "Supabase",
    "ClickHouse",

    # === Cloud / infra / DevOps ===
    "AWS", "GCP", "Azure", "Google Cloud", "Lambda", "EC2", "S3", "ECS",
    "EKS", "Kubernetes", "K8s", "Docker", "Terraform", "Ansible", "Pulumi",
    "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD",
    "Helm", "Vault", "Istio", "Prometheus", "Grafana", "Datadog",
    "New Relic", "Splunk", "PagerDuty", "CI/CD", "DevOps", "SRE",
    "Site Reliability Engineering",

    # === ML / AI ===
    "TensorFlow", "PyTorch", "Keras", "scikit-learn", "JAX", "MXNet",
    "Hugging Face", "transformers", "LangChain", "LlamaIndex", "OpenAI",
    "Anthropic", "Claude", "GPT", "LLM", "RAG", "fine-tuning",
    "machine learning", "deep learning", "neural networks", "CNN", "RNN",
    "transformer", "BERT", "diffusion models",
    "computer vision", "NLP", "natural language processing",
    "speech recognition", "reinforcement learning",
    "MLOps", "MLflow", "Weights & Biases", "Vertex AI", "SageMaker",
    "AI", "artificial intelligence", "generative AI", "data science",

    # === Hardware / systems / HPC ===
    "GPU", "CUDA", "TPU", "CPU", "FPGA", "ASIC", "RTL", "Verilog", "VHDL",
    "SystemVerilog", "embedded systems", "firmware", "device drivers",
    "Linux kernel", "low-level programming", "memory management",
    "concurrency", "distributed systems", "high-performance computing",
    "HPC", "OpenCL", "OneAPI", "NCCL", "TensorRT",

    # === Data engineering / analytics ===
    "pandas", "NumPy", "SciPy", "Spark", "PySpark", "Hadoop", "Hive",
    "Airflow", "dbt", "Kafka", "Flink", "Beam", "Dataflow",
    "ETL", "ELT", "data warehouse", "data lake", "data pipeline",
    "Tableau", "Power BI", "Looker", "Metabase", "Superset",
    "data engineering", "data analytics", "statistical analysis",
    "statistics", "regression", "Bayesian", "hypothesis testing",

    # === Security ===
    "cybersecurity", "penetration testing", "SOC", "SIEM", "OWASP",
    "encryption", "OAuth", "SAML", "Zero Trust", "IAM",

    # === Networking / web ===
    "TCP/IP", "HTTP", "HTTPS", "REST", "gRPC", "WebSocket", "DNS",
    "load balancing", "CDN",

    # === Methodologies ===
    "Agile", "Scrum", "Kanban", "TDD", "BDD", "code review",
    "pair programming", "system design", "design patterns",

    # === Product / business / PM ===
    "product management", "product strategy", "roadmapping",
    "user research", "A/B testing", "growth", "OKRs", "KPIs",
    "stakeholder management", "Jira", "Confluence", "Asana", "Notion",
    "Linear", "project management", "PMP",

    # === Marketing ===
    "SEO", "SEM", "Google Ads", "Facebook Ads", "content marketing",
    "email marketing", "marketing automation", "HubSpot", "Marketo",
    "Mailchimp", "Google Analytics", "GA4", "Mixpanel", "Segment",
    "Amplitude",

    # === Sales / CRM ===
    "Salesforce", "Outreach", "Gong", "lead generation",
    "account management", "B2B", "B2C",

    # === Design ===
    "Figma", "Sketch", "Adobe XD", "InVision", "Photoshop", "Illustrator",
    "After Effects", "Premiere", "UI", "UX", "UI/UX", "user experience",
    "user interface", "wireframing", "prototyping", "design systems",
    "accessibility", "WCAG",

    # === Finance / accounting ===
    "financial modeling", "DCF", "valuation", "FP&A", "M&A",
    "equity research", "investment banking", "private equity",
    "venture capital", "CPA", "CFA", "GAAP", "IFRS",
    "QuickBooks", "SAP",

    # === Operations / supply chain ===
    "operations", "logistics", "supply chain", "procurement",
    "Six Sigma", "Lean", "ERP",

    # === Biology / healthcare (preserved) ===
    "CRISPR", "scRNA-seq", "RNA-seq", "single-cell", "flow cytometry",
    "immunohistochemistry", "IHC", "Western blot", "qPCR", "RT-PCR",
    "cell culture", "mouse models", "in vivo", "in vitro",
    "tumor microenvironment", "oncology", "cancer biology", "immunology",
    "immuno-oncology", "bioinformatics", "genomics", "proteomics",
    "metabolomics", "next-generation sequencing", "NGS",
    "whole exome sequencing", "ChIP-seq", "ATAC-seq", "epigenetics",
    "gene editing", "molecular biology", "biochemistry", "cell signaling",
    "drug discovery", "clinical trials", "GLP", "GMP",
    "confocal microscopy", "fluorescence microscopy", "FACS",
    "protein purification", "cloning", "transfection",
    "ELISA", "mass spectrometry", "LC-MS", "NMR",
    "stem cells", "organoids", "3D cell culture",
    "CAR-T", "checkpoint inhibitors", "immunotherapy",
    "pharmacology", "toxicology", "pathology",
    "biomarkers", "liquid biopsy", "ctDNA",
    "GMP manufacturing", "process development",
    "regulatory affairs", "FDA", "IND",

    # === Writing / general ===
    "scientific writing", "grant writing", "technical writing", "research",
]


# ── Job title patterns — multi-domain ────────────────────────────────────────
# Patterns return the whole match; build_queries uses each as a search phrase.
JOB_TITLE_PATTERNS = [
    # ── Tech ─────────────────────────────────────────────────────
    r"(?:senior|staff|principal|lead|junior)?\s*software\s+engineer",
    r"(?:senior|staff|principal|lead|junior)?\s*software\s+developer",
    r"(?:senior|staff|principal|lead|junior)?\s*(?:full[- ]stack|front[- ]end|frontend|back[- ]end|backend|mobile)\s+(?:engineer|developer)",
    r"(?:senior|staff|principal|lead|junior)?\s*(?:ios|android)\s+(?:engineer|developer)",
    r"(?:machine\s+learning|deep\s+learning|computer\s+vision|nlp)\s+(?:engineer|scientist|researcher)",
    r"\b(?:ml|ai)\s+(?:engineer|scientist|researcher)\b",
    r"data\s+(?:scientist|engineer|analyst)",
    r"(?:devops|sre|site\s+reliability|platform|infrastructure|cloud|gpu|performance|security|hardware|systems|firmware|embedded)\s+engineer",
    r"engineering\s+manager",
    r"(?:tech|technical)\s+lead",
    r"(?:chief|principal|solutions?|enterprise)\s+architect",
    r"(?:product|technical\s+product|associate\s+product|group\s+product)\s+manager",
    r"(?:ui|ux|product|graphic|interaction)\s+designer",
    r"(?:analytics|business|bi|operations|financial|equity\s+research)\s+analyst",

    # ── Healthcare / research (preserved) ────────────────────────
    r"postdoc(?:toral)?\s+(?:fellow|researcher|scientist|position)?",
    r"research\s+(?:scientist|associate|fellow|analyst)",
    r"(?:senior|staff|principal)\s+scientist",
    r"lab(?:oratory)?\s+(?:manager|director|technician)",
    r"bioinformatics\s+(?:scientist|analyst|engineer)",
    r"clinical\s+(?:scientist|researcher|trial)",
    r"(?:medical|scientific)\s+(?:director|advisor|liaison)",

    # ── Business / marketing / sales ─────────────────────────────
    r"(?:marketing|growth|content|product\s+marketing|brand)\s+(?:manager|strategist|lead|director)",
    r"(?:operations|business)\s+manager",
    r"(?:strategy|management)\s+consultant",
    r"account\s+(?:executive|manager)",
]


# ── File extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(pages)
    except Exception:
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    return ""


# ── Skill extraction (word-boundary aware) ───────────────────────────────────

def _find_skill_index(text: str, skill: str) -> int | None:
    """Return the index of `skill` as a 'whole token' in `text`, or None.

    "Whole token" means the characters immediately before and after the match
    aren't alphanumeric or underscore, so:
      * "PI"    matches "PI" but not "API", "Spider", "Pixel"
      * "R"     matches "R" but not "for", "research"
      * "AI"    matches "AI" but not "fair", "stainless"
      * "C++"   matches "C++" (the `\\b` regex form fails here because '+'
                isn't a word char; the manual neighbor check handles it)

    Short acronyms (≤3 chars) are matched case-sensitively so "PI" doesn't
    eat the 'pi' in "Pixel"; longer terms are case-insensitive.
    """
    if not skill or not text:
        return None
    case_sensitive = len(skill) <= 3
    needle = skill if case_sensitive else skill.lower()
    haystack = text if case_sensitive else text.lower()
    start = 0
    n = len(haystack)
    L = len(needle)
    while True:
        i = haystack.find(needle, start)
        if i == -1:
            return None
        left_ok = (i == 0) or not (haystack[i - 1].isalnum() or haystack[i - 1] == "_")
        end = i + L
        right_ok = (end == n) or not (haystack[end].isalnum() or haystack[end] == "_")
        if left_ok and right_ok:
            return i
        start = i + 1


def extract_skills(text: str) -> list[str]:
    """Skills found in `text`, ordered by first appearance in the resume.

    Word-boundary matching keeps short acronyms (PI, R, IND, AI, GPU) from
    falsely matching substrings of unrelated words.
    """
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for skill in SKILL_KEYWORDS:
        if skill in seen:
            continue
        idx = _find_skill_index(text, skill)
        if idx is not None:
            found.append((idx, skill))
            seen.add(skill)
    found.sort(key=lambda x: x[0])
    return [s for _, s in found]


def extract_job_titles(text: str) -> list[str]:
    """Job-title-shaped phrases found in `text`, deduped, lowered."""
    found: list[str] = []
    text_lower = text.lower()
    for pattern in JOB_TITLE_PATTERNS:
        for m in re.finditer(pattern, text_lower):
            cleaned = re.sub(r"\s+", " ", m.group(0)).strip()
            if cleaned and cleaned not in found:
                found.append(cleaned)
    return found


def extract_location_preferences(text: str) -> list[str]:
    """Find location mentions in the text."""
    locations: list[str] = []
    location_patterns = [
        r"(?:Bay Area|San Francisco|South San Francisco|San Jose|Palo Alto|"
        r"Mountain View|Sunnyvale|Santa Clara|Redwood City|Emeryville|"
        r"Berkeley|Oakland|Foster City|San Mateo|Fremont|Hayward|"
        r"San Diego|Los Angeles|Sacramento|Seattle|Portland|Austin|"
        r"Denver|Boston|Cambridge|New York|NYC|Brooklyn|Chicago|Atlanta|"
        r"Phoenix|Dallas|Houston|California|CA)",
    ]
    for pattern in location_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        locations.extend(matches)
    # Preserve first occurrence; don't enforce a default location here — the
    # user picks one in the UI.
    seen, ordered = set(), []
    for loc in locations:
        if loc not in seen:
            seen.add(loc)
            ordered.append(loc)
    return ordered


def build_queries(skills: list[str], titles: list[str], locations: list[str]) -> list[str]:
    """Build job-search queries for a specific set of locations.

    Skills and titles come from the resume; locations are user-selected
    so the same resume can search Bay Area today and Boston tomorrow.
    """
    queries: list[str] = []
    top_skills = (skills or [])[:5]
    skill_str = " ".join(top_skills[:3]) if top_skills else ""

    locs = locations or ["United States"]
    for loc in locs[:3]:
        if skill_str:
            queries.append(f"{skill_str} jobs {loc}")
        for title in (titles or [])[:3]:
            queries.append(f"{title} jobs {loc}")
            if skill_str:
                queries.append(f"{title} {skill_str} {loc}")
        if not titles and not skill_str:
            queries.append(f"jobs in {loc}")

    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


def build_search_profile(resume_text: str, cover_letter_text: str = "") -> dict:
    """Build a search profile from resume and cover letter text."""
    combined = f"{resume_text}\n{cover_letter_text}"
    skills = extract_skills(combined)
    titles = extract_job_titles(combined)
    locations = extract_location_preferences(combined)
    queries = build_queries(skills, titles, locations or ["United States"])

    return {
        "skills": skills,
        "titles": titles,
        "locations": locations,
        "queries": queries,
    }
