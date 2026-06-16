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
def get_user(user_id: str) -> Optional[dict[str, Any]]:
    res = get_supabase().table("users").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None


def create_user(user_id: str, email: str, name: str) -> dict[str, Any]:
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


def get_household(household_id: str) -> Optional[dict[str, Any]]:
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
# Supported dietary labels (a meal lists the ones it COMPLIES with). A user's
# dietary_restrictions are matched against these; tags are approximate for MVP.
DIETARY_LABELS = (
    "vegetarian", "vegan", "pescatarian",
    "gluten_free", "dairy_free", "pork_free", "nut_free",
)

# Hardcoded catalog (10 meals). meal_id values are the string ids below and are
# stored as-is on swipes/matches. Images are real photos hosted on Wikimedia
# Commons (verified 200 / image/jpeg).
MEALS: list[dict[str, Any]] = [
    {"id": "1", "name": "Loco Moco", "description": "Rice topped with a hamburger patty, fried egg, and brown gravy.", "cuisine": "Hawaiian", "dietary": ["pork_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Loco_moco_%2832605169782%29.jpg/960px-Loco_moco_%2832605169782%29.jpg"},
    {"id": "2", "name": "Chicken Katsu", "description": "Panko-crusted fried chicken cutlet with tonkatsu sauce.", "cuisine": "Japanese", "dietary": ["pork_free", "dairy_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Matsunoya_W_Mega_Chicken_Katsu_Set_20200923-04.jpg/960px-Matsunoya_W_Mega_Chicken_Katsu_Set_20200923-04.jpg"},
    {"id": "3", "name": "Kalua Pork", "description": "Slow-roasted shredded pork with smoky flavor.", "cuisine": "Hawaiian", "dietary": ["gluten_free", "dairy_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Roasted_puaa.jpg/960px-Roasted_puaa.jpg"},
    {"id": "4", "name": "Spam Musubi", "description": "Grilled Spam over rice wrapped in nori.", "cuisine": "Hawaiian", "dietary": ["dairy_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Homemade_Spam_Musubi.jpg/960px-Homemade_Spam_Musubi.jpg"},
    {"id": "5", "name": "Beef Tacos", "description": "Seasoned beef in corn tortillas with salsa.", "cuisine": "Mexican", "dietary": ["pork_free", "gluten_free", "dairy_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/001_Tacos_de_carnitas%2C_carne_asada_y_al_pastor.jpg/960px-001_Tacos_de_carnitas%2C_carne_asada_y_al_pastor.jpg"},
    {"id": "6", "name": "Margherita Pizza", "description": "Tomato, fresh mozzarella, and basil on a thin crust.", "cuisine": "Italian", "dietary": ["vegetarian", "pescatarian", "pork_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Pizza_Margherita_stu_spivack.jpg/960px-Pizza_Margherita_stu_spivack.jpg"},
    {"id": "7", "name": "Pad Thai", "description": "Stir-fried rice noodles with shrimp, peanuts, and tamarind.", "cuisine": "Thai", "dietary": ["pescatarian", "pork_free", "gluten_free", "dairy_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Phat_Thai_kung_Chang_Khien_street_stall.jpg/960px-Phat_Thai_kung_Chang_Khien_street_stall.jpg"},
    {"id": "8", "name": "Chicken Tikka Masala", "description": "Grilled chicken in a creamy spiced tomato sauce.", "cuisine": "Indian", "dietary": ["pork_free", "gluten_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Chicken_tikka_masala_%28cropped%29.jpg/960px-Chicken_tikka_masala_%28cropped%29.jpg"},
    {"id": "9", "name": "Bibimbap", "description": "Rice bowl with vegetables, beef, egg, and gochujang.", "cuisine": "Korean", "dietary": ["pork_free", "dairy_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Dolsot-bibimbap.jpg/960px-Dolsot-bibimbap.jpg"},
    {"id": "10", "name": "Cheeseburger", "description": "Grilled beef patty with cheese, lettuce, and tomato.", "cuisine": "American", "dietary": ["pork_free", "nut_free"], "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cheeseburger.jpg/960px-Cheeseburger.jpg"},
]


def get_meals() -> list[dict[str, Any]]:
    """Return the hardcoded meal catalog."""
    return MEALS


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
