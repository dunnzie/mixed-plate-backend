"""Supabase connection and query helpers for Mixed Plate."""
import os
from functools import lru_cache
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def credentials_configured() -> bool:
    """True when both Supabase env vars are present."""
    return bool(SUPABASE_URL and SUPABASE_KEY)


@lru_cache
def get_supabase() -> Client:
    """Return a cached Supabase client.

    Raises a clear error if credentials are missing so the failure is obvious
    at request time rather than a confusing stack trace.
    """
    if not credentials_configured():
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set. "
            "Copy .env.example to .env and fill in your project credentials."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# --------------------------------------------------------------------------- #
# User helpers
# --------------------------------------------------------------------------- #
def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    res = get_supabase().table("users").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None


def create_user_profile(user_id: str, email: str, name: str) -> dict[str, Any]:
    profile = {"id": user_id, "email": email, "name": name}
    get_supabase().table("users").insert(profile).execute()
    return profile


def set_user_household(user_id: str, household_id: str) -> None:
    get_supabase().table("users").update({"household_id": household_id}).eq(
        "id", user_id
    ).execute()


def get_household_members(household_id: str) -> list[dict[str, Any]]:
    res = (
        get_supabase()
        .table("users")
        .select("id, email, name")
        .eq("household_id", household_id)
        .execute()
    )
    return res.data


# --------------------------------------------------------------------------- #
# Preferences helpers
# --------------------------------------------------------------------------- #
def get_user_preferences(user_id: str) -> Optional[dict[str, Any]]:
    res = (
        get_supabase()
        .table("user_preferences")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None


def upsert_user_preferences(
    user_id: str, dietary: list[str], cuisines: list[str]
) -> dict[str, Any]:
    res = (
        get_supabase()
        .table("user_preferences")
        .upsert(
            {
                "user_id": user_id,
                "dietary_restrictions": dietary,
                "favorite_cuisines": cuisines,
            },
            on_conflict="user_id",
        )
        .execute()
    )
    return res.data[0]


# --------------------------------------------------------------------------- #
# Household helpers
# --------------------------------------------------------------------------- #
def create_household(name: str, invite_code: str, created_by: str) -> dict[str, Any]:
    res = (
        get_supabase()
        .table("households")
        .insert({"name": name, "invite_code": invite_code, "created_by": created_by})
        .execute()
    )
    return res.data[0]


def get_household_by_id(household_id: str) -> Optional[dict[str, Any]]:
    res = (
        get_supabase()
        .table("households")
        .select("*")
        .eq("id", household_id)
        .execute()
    )
    return res.data[0] if res.data else None


def get_household_by_invite_code(invite_code: str) -> Optional[dict[str, Any]]:
    res = (
        get_supabase()
        .table("households")
        .select("*")
        .eq("invite_code", invite_code)
        .execute()
    )
    return res.data[0] if res.data else None


# --------------------------------------------------------------------------- #
# Meal / swipe / match helpers
# --------------------------------------------------------------------------- #
def list_meals() -> list[dict[str, Any]]:
    return get_supabase().table("meals").select("*").execute().data


def upsert_swipe(
    user_id: str, household_id: str, meal_id: str, liked: bool
) -> dict[str, Any]:
    res = (
        get_supabase()
        .table("swipes")
        .upsert(
            {
                "user_id": user_id,
                "household_id": household_id,
                "meal_id": meal_id,
                "liked": liked,
            },
            on_conflict="user_id,meal_id",
        )
        .execute()
    )
    return res.data[0]


def get_meal_likes(household_id: str, meal_id: str) -> list[dict[str, Any]]:
    res = (
        get_supabase()
        .table("swipes")
        .select("user_id")
        .eq("household_id", household_id)
        .eq("meal_id", meal_id)
        .eq("liked", True)
        .execute()
    )
    return res.data


def get_match(household_id: str, meal_id: str) -> Optional[dict[str, Any]]:
    res = (
        get_supabase()
        .table("matches")
        .select("*")
        .eq("household_id", household_id)
        .eq("meal_id", meal_id)
        .execute()
    )
    return res.data[0] if res.data else None


def create_match(household_id: str, meal_id: str) -> dict[str, Any]:
    res = (
        get_supabase()
        .table("matches")
        .insert({"household_id": household_id, "meal_id": meal_id})
        .execute()
    )
    return res.data[0]


def list_matches(household_id: str) -> list[dict[str, Any]]:
    res = (
        get_supabase()
        .table("matches")
        .select("*")
        .eq("household_id", household_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data
