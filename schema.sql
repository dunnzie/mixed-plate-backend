-- ============================================================================
-- Mixed Plate — complete database schema + Row Level Security policies.
-- Paste this whole file into the Supabase SQL editor and run it.
--
-- The backend talks to Supabase with the anon key, so Postgres sees those
-- requests as the `anon` role. RLS is therefore enabled on every table with
-- policies that grant the access the backend needs (anon + authenticated).
-- This is fine for an MVP where the FastAPI backend is the only client and it
-- enforces auth at the application layer. For production, prefer the
-- service_role key (which bypasses RLS) or tighten these policies to per-user.
--
-- This script is idempotent: it can be re-run safely.
-- ============================================================================

-- ── Tables ──────────────────────────────────────────────────────────────────

create table if not exists households (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    invite_code text unique not null,
    created_by uuid not null,
    created_at timestamptz default now()
);

create table if not exists users (
    id uuid primary key,                 -- matches auth.users.id
    email text unique not null,
    name text not null,
    household_id uuid references households (id),
    created_at timestamptz default now()
);

create table if not exists user_preferences (
    user_id uuid primary key references users (id),
    dietary_restrictions text[] default '{}',
    favorite_cuisines text[] default '{}',
    updated_at timestamptz default now()
);

-- Meals are served from a hardcoded catalog in database.py (MEALS), so there
-- is no meals table. meal_id below is the string id from that catalog.

create table if not exists swipes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id),
    household_id uuid not null references households (id),
    meal_id text not null,
    liked boolean not null,
    created_at timestamptz default now(),
    unique (user_id, meal_id)
);

create table if not exists matches (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references households (id),
    meal_id text not null,
    created_at timestamptz default now(),
    unique (household_id, meal_id)
);

-- ── Row Level Security ──────────────────────────────────────────────────────
-- Enable RLS on every table, then add a permissive policy granting full access
-- to the anon and authenticated roles. Without these, the anon key cannot
-- insert and signup fails with a 500 / RLS error.

alter table households       enable row level security;
alter table users            enable row level security;
alter table user_preferences enable row level security;
alter table swipes           enable row level security;
alter table matches          enable row level security;

-- households
drop policy if exists "mp_households_all" on households;
create policy "mp_households_all" on households
    for all to anon, authenticated
    using (true) with check (true);

-- users
drop policy if exists "mp_users_all" on users;
create policy "mp_users_all" on users
    for all to anon, authenticated
    using (true) with check (true);

-- user_preferences
drop policy if exists "mp_user_preferences_all" on user_preferences;
create policy "mp_user_preferences_all" on user_preferences
    for all to anon, authenticated
    using (true) with check (true);

-- swipes
drop policy if exists "mp_swipes_all" on swipes;
create policy "mp_swipes_all" on swipes
    for all to anon, authenticated
    using (true) with check (true);

-- matches
drop policy if exists "mp_matches_all" on matches;
create policy "mp_matches_all" on matches
    for all to anon, authenticated
    using (true) with check (true);
