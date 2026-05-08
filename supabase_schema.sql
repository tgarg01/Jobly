-- Run this in the Supabase SQL editor.
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
    titles text,           -- JSON-encoded list[str] (v2)
    preferred_location text,  -- v2
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
    user_email text,
    status text,    -- v2: null / waiting / pass / fail
    config_id bigint  -- v3: which configuration this job belongs to
);

-- v3: per-user search configurations (each is its own tracker).
create table if not exists public.configs (
    id bigserial primary key,
    user_email text not null,
    name text not null,
    location text,
    radius_miles int,
    override_resume_text text,
    override_cover_letter_text text,
    override_resume_filename text,
    override_cover_letter_filename text,
    override_skills text,    -- JSON-encoded list[str]
    override_titles text,    -- JSON-encoded list[str]
    created_at date default current_date,
    updated_at date default current_date,
    unique (user_email, name)
);

-- Migrations for older deployments:
alter table public.jobs add column if not exists user_email text;
alter table public.jobs add column if not exists status text;
alter table public.jobs add column if not exists config_id bigint;
alter table public.user_profiles add column if not exists titles text;
alter table public.user_profiles add column if not exists preferred_location text;

-- RLS: open policies (no password auth in app yet — gated by knowing the email).
alter table public.user_profiles enable row level security;
alter table public.jobs enable row level security;
alter table public.configs enable row level security;

drop policy if exists "user_profiles all" on public.user_profiles;
create policy "user_profiles all" on public.user_profiles
    for all using (true) with check (true);

drop policy if exists "jobs all" on public.jobs;
create policy "jobs all" on public.jobs
    for all using (true) with check (true);

drop policy if exists "configs all" on public.configs;
create policy "configs all" on public.configs
    for all using (true) with check (true);
