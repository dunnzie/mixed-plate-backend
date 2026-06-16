-- Mixed Plate database schema (run in the Supabase SQL editor).
-- Profiles are keyed to Supabase Auth users via the shared UUID.

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
