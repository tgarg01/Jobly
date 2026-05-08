-- Run this in the Supabase SQL editor once.
-- Safe to re-run: every statement is idempotent.

create table if not exists public.user_profiles (
    id bigserial primary key,
    email text unique not null,
    resume_text text,
    cover_letter_text text,
    resume_filename text,
    cover_letter_filename text,
    skills text,           -- JSON-encoded list[str]
    search_queries text,   -- JSON-encoded list[str]
    created_at date default current_date,
    updated_at date default current_date
);

create table if not exists public.jobs (
    id bigserial primary key,
    company text,
    job_title text,
    location text,
    job_link text,
    posted_date date,
    applied_date date,
    contact_info text,
    job_type text,
    key_skills text,
    comments text,
    fit_score int,
    salary text,
    added_on date default current_date,
    is_active boolean default true,
    user_email text
);

-- Add user_email if an older `jobs` table is missing it.
alter table public.jobs add column if not exists user_email text;

-- RLS: open policies (no password auth in app yet — gated by knowing the email).
alter table public.user_profiles enable row level security;
alter table public.jobs enable row level security;

drop policy if exists "user_profiles all" on public.user_profiles;
create policy "user_profiles all" on public.user_profiles
    for all using (true) with check (true);

drop policy if exists "jobs all" on public.jobs;
create policy "jobs all" on public.jobs
    for all using (true) with check (true);
