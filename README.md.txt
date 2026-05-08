Taruna's Job Tracker — Streamlit App
What This Is
A fully self-contained Streamlit web app for Taruna Saini to track cancer biology / oncology job opportunities in the California Bay Area. No Google Drive. No Excel. No spreadsheet auth headaches.


* Frontend: Streamlit (Python)
* Database: Supabase (free PostgreSQL — no card required)
* Deployment: Streamlit Community Cloud (free)
* AI Scheduler: The job-finder skill appends new jobs directly via the Supabase API


________________


Architecture
┌─────────────────────────┐        ┌──────────────────────┐


│  Streamlit Community    │◄──────►│  Supabase (Postgres) │


│  Cloud  (app.py)        │        │  jobs table          │


└─────────────────────────┘        └──────────────────────┘


           ▲                                  ▲


           │                                  │


    Taruna uses the UI            AI job-finder scheduler


    to mark Applied,              inserts new rows via


    add Comments, etc.            Supabase REST API


Why Supabase?


* Free tier: 500 MB database, unlimited API calls
* No auth token setup — just an ANON_KEY and URL in secrets
* Works perfectly from both Streamlit and Python scripts
* No file system dependency — data persists across Streamlit deployments


________________


Database Schema (Supabase)
Table: jobs
create table jobs (


  id           serial primary key,


  company      text not null,


  job_title    text not null,


  location     text,


  job_link     text,


  posted_date  text,


  applied_date text,           -- filled by Taruna


  contact_info text,


  job_type     text,           -- 'Postdoc' or 'Industry'


  key_skills   text,


  comments     text,           -- filled by Taruna


  fit_score    integer,        -- 0-100, set by AI scheduler


  salary       text,


  added_on     date default current_date,


  is_active    boolean default true


);


Run this SQL once in the Supabase SQL Editor after creating the project.


________________


App Pages
Page 1 — Dashboard (pages/1_Dashboard.py)
* 4 summary cards: Total Jobs | Applied | Pending | Expired/Irrelevant
* Donut chart: Postdoc vs Industry split
* Bar chart: Jobs by company (top 10)
* Timeline: Jobs added over time (by added_on)
* Skill cloud: Most common skills across all listings
Page 2 — Job Board (pages/2_Job_Board.py)
* Full table of all active jobs
* Filters: Job Type, Applied status, Company, keyword search
* Color coding:
   * 🟢 Applied
   * ⚪ Not yet applied
   * 🔴 Expired / irrelevant (flagged in Comments)
* Inline actions per row:
   * ✅ Mark Applied (sets today's date in applied_date)
   * 💬 Add / Edit Comment
   * 🔗 Open Job Link (new tab)
   * 🗑 Hide job (sets is_active = false)
Page 3 — Add Job (pages/3_Add_Job.py)
* Manual entry form for all fields
* Duplicate check before inserting (Company + Job Title)
* Pre-fills Location as "Bay Area, CA" by default
* Dropdown for Job Type: Postdoc / Industry
Page 4 — Insights (pages/4_Insights.py)
* Jobs Taruna flagged as "link not working", "no longer exists", "irrelevant" — listed for cleanup
* Application funnel: Added → Applied → (outcome)
* Export all active jobs as a .csv download (no Excel needed)


________________


Repository Structure
taruna-job-tracker/


├── app.py                     # Entry point — sets page config, renders home


├── pages/


│   ├── 1_Dashboard.py


│   ├── 2_Job_Board.py


│   ├── 3_Add_Job.py


│   └── 4_Insights.py


├── utils/


│   ├── db.py                  # All Supabase read/write functions


│   ├── deduplicate.py         # Duplicate detection


│   └── constants.py           # Column names, job types, etc.


├── requirements.txt


├── .streamlit/


│   └── secrets.toml           # Supabase keys (NOT committed to git)


└── README.md


________________


utils/db.py — Core Database Helper
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


________________


requirements.txt
streamlit>=1.32.0


supabase>=2.4.0


pandas>=2.0.0


plotly>=5.18.0


________________


.streamlit/secrets.toml (local dev — do NOT commit)
[supabase]


url = "https://your-project-ref.supabase.co"


anon_key = "your-anon-key-here"


In Streamlit Community Cloud, paste these same values into App Settings → Secrets.


________________


Setup Steps
1. Create Supabase Project (5 minutes)
1. Go to supabase.com → New Project (free)
2. Copy your Project URL and anon public key from Settings → API
3. Open the SQL Editor → run the create table jobs (...) SQL above
2. Create GitHub Repo
git init taruna-job-tracker


cd taruna-job-tracker


# add all files from this structure


git remote add origin https://github.com/YOUR_USERNAME/taruna-job-tracker.git


git push -u origin main
3. Deploy on Streamlit Community Cloud
1. Go to share.streamlit.io → sign in with GitHub
2. New app → select repo taruna-job-tracker, branch main, file app.py
3. Advanced settings → Secrets → paste the [supabase] block
4. Click Deploy


App goes live at: https://taruna-job-tracker.streamlit.app
4. Seed Existing Jobs
Run a one-time Python script to import Taruna's 36 existing jobs from the Google Sheet into Supabase (or paste them manually via the Add Job page). This is optional — the app can start fresh.


________________


AI Scheduler Integration
The job-finder scheduled task inserts new jobs using the same Supabase credentials:


from supabase import create_client


client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def insert_if_new(job: dict) -> bool:


    """Returns True if inserted, False if duplicate."""


    existing = client.table("jobs").select("id") \


        .eq("company", job["company"]) \


        .eq("job_title", job["job_title"]) \


        .execute()


    if existing.data:


        return False


    client.table("jobs").insert(job).execute()


    return True


The scheduler stores SUPABASE_URL and SUPABASE_ANON_KEY as environment variables or in Cowork secrets — no Google auth required.


________________


Job Fields Reference
Field
	Who fills it
	Notes
	company
	AI scheduler
	e.g. "Genentech"
	job_title
	AI scheduler
	e.g. "Postdoctoral Fellow – Oncology"
	location
	AI scheduler
	e.g. "South San Francisco, CA"
	job_link
	AI scheduler
	Direct apply URL
	posted_date
	AI scheduler
	e.g. "2026-05-07"
	applied_date
	Taruna
	Click ✅ or enter manually
	contact_info
	AI scheduler
	PI email / recruiter name if found
	job_type
	AI scheduler
	"Postdoc" or "Industry"
	key_skills
	AI scheduler
	"CRISPR, tumor microenvironment, scRNA-seq"
	comments
	Taruna
	Free text feedback
	fit_score
	AI scheduler
	0–100
	salary
	AI scheduler
	If listed publicly
	

________________


Stretch Goals
* Email digest to Taruna when 5+ new jobs are added (via smtplib or Resend API)
* One-click link checker — auto-flag rows where job_link returns 404/410
* Fit score re-ranking based on Taruna's feedback patterns
* Password protection using streamlit-authenticator
* Mobile layout optimization


________________


Key People
Person
	Role
	Contact
	Taruna Saini
	App user / job seeker
	tarunaut.saini700@gmail.com
	Tushargarg
	App builder / maintainer
	tushgarg20@gmail.com