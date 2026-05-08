# Jobly — Project Context

## What This Is
A Streamlit web app for tracking cancer biology / oncology job opportunities. Users sign in with email, upload their resume, and the app searches job boards (LinkedIn, Indeed, Glassdoor) using DuckDuckGo to find matching positions. Jobs are saved to Supabase and users can track applications like a diary.

## Tech Stack
- **Frontend:** Streamlit (Python)
- **Database:** Supabase (free PostgreSQL) — project ref: `quwxbroycezvzluumpcp`
- **Job Search:** `ddgs` package (DuckDuckGo search)
- **Resume Parsing:** `pdfplumber` (PDF), `python-docx` (DOCX)
- **Deployment:** Streamlit Community Cloud (auto-deploys from GitHub `tgarg01/Jobly`, branch `main`)
- **Supabase credentials** are in `.streamlit/secrets.toml` (gitignored) and also configured in Streamlit Cloud's app secrets

## Architecture
```
app.py                  — Home page: email login, resume upload, job search button
pages/1_Dashboard.py    — Summary cards, charts (donut, bar, timeline, skill cloud)
pages/2_Job_Board.py    — Job tracker diary: browse, filter, notes, mark applied, export CSV
pages/3_Add_Job.py      — REMOVED (stub file, can be deleted)
pages/4_Insights.py     — REMOVED (stub file, can be deleted)
utils/db.py             — All Supabase CRUD (jobs + user_profiles tables)
utils/job_search.py     — DuckDuckGo job search, result parsing, fit scoring
utils/resume_parser.py  — Extract text from PDF/DOCX, identify skills, build search queries
utils/constants.py      — Shared constants (job types, flag keywords)
utils/deduplicate.py    — Duplicate detection helper
```

## Database Schema (Supabase)

### Table: `jobs`
```sql
id, company, job_title, location, job_link, posted_date, applied_date,
contact_info, job_type, key_skills, comments, fit_score, salary,
added_on (date), is_active (boolean), user_email (text)
```

### Table: `user_profiles`
```sql
id, email (unique), resume_text, cover_letter_text, resume_filename,
cover_letter_filename, skills (JSON string), search_queries (JSON string),
created_at, updated_at
```

Both tables have RLS enabled with public read/insert/update/delete policies.

## Pending Work / Known Issues
1. **Job search may return 0 results on Streamlit Cloud** — DuckDuckGo can rate-limit or block cloud server IPs. The `ddgs` package works locally but may fail in production. The save loop in `app.py` now surfaces insert errors and counts in the status box so failures are visible. Adding a fallback search source (JSearch / SerpAPI) is still open.
2. **SQL schema** — Confirmed required schema is in `supabase_schema.sql`. Run it once in the Supabase SQL editor. Includes `user_profiles`, `jobs.user_email`, and open RLS policies.
3. ~~Delete stub pages~~ — Done. `pages/3_Add_Job.py` and `pages/4_Insights.py` removed.
4. **Login persistence** — `app.py` now stores email in `st.query_params["u"]` so browser refresh keeps the user logged in and reloads their saved resume from `user_profiles`.
5. **Stretch goals from spec:** email digest, link checker, fit score re-ranking, password auth, mobile optimization.

## Deployment Flow
1. Push to `main` branch on GitHub (`tgarg01/Jobly`)
2. Streamlit Cloud auto-redeploys
3. Supabase secrets are configured in Streamlit Cloud app settings

## Key Commands
```bash
# Run locally
pip install -r requirements.txt
streamlit run app.py

# Deploy
git add . && git commit -m "message" && git push
```
