"""Mixed Plate — FastAPI backend.

A household meal-matching app: members swipe on meals, and when everyone in a
household likes the same meal it becomes a "match".

Run locally:
    python3 main.py
"""
import secrets

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from database import get_supabase
from models import (
    AuthResponse,
    Household,
    HouseholdCreate,
    HouseholdJoin,
    LoginRequest,
    Match,
    Meal,
    SignupRequest,
    Swipe,
    SwipeCreate,
    SwipeResponse,
    User,
)

app = FastAPI(title="Mixed Plate", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Auth helpers
# --------------------------------------------------------------------------- #
def get_current_user(authorization: str = Header(...)) -> User:
    """Resolve the current user from a Bearer access token."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    token = authorization.split(" ", 1)[1]
    supabase = get_supabase()

    try:
        auth_user = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token."
        )
    if auth_user is None or auth_user.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token."
        )

    uid = auth_user.user.id
    row = supabase.table("users").select("*").eq("id", uid).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return User(**row.data)


def require_household(user: User) -> str:
    """Return the user's household id or raise if they have not joined one."""
    if not user.household_id:
        raise HTTPException(
            status_code=400,
            detail="You must create or join a household first.",
        )
    return user.household_id


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/")
def root():
    return {"app": "Mixed Plate", "status": "ok"}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.post("/auth/signup", response_model=AuthResponse)
def signup(body: SignupRequest):
    supabase = get_supabase()
    try:
        res = supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if res.user is None:
        raise HTTPException(status_code=400, detail="Signup failed.")

    # Create the application-level profile row.
    profile = {
        "id": res.user.id,
        "email": body.email,
        "name": body.name,
    }
    supabase.table("users").insert(profile).execute()

    if res.session is None:
        raise HTTPException(
            status_code=200,
            detail="Signup succeeded but email confirmation is required.",
        )

    return AuthResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user=User(**profile),
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    supabase = get_supabase()
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if res.user is None or res.session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    row = (
        supabase.table("users")
        .select("*")
        .eq("id", res.user.id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="User profile not found.")

    return AuthResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user=User(**row.data),
    )


# --------------------------------------------------------------------------- #
# Households
# --------------------------------------------------------------------------- #
@app.post("/households", response_model=Household)
def create_household(body: HouseholdCreate, user: User = Depends(get_current_user)):
    supabase = get_supabase()
    invite_code = secrets.token_hex(4).upper()  # 8-char shareable code

    res = (
        supabase.table("households")
        .insert(
            {
                "name": body.name,
                "invite_code": invite_code,
                "created_by": user.id,
            }
        )
        .execute()
    )
    household = res.data[0]

    # Creator automatically joins the household they made.
    supabase.table("users").update({"household_id": household["id"]}).eq(
        "id", user.id
    ).execute()

    return Household(**household)


@app.post("/households/join", response_model=Household)
def join_household(body: HouseholdJoin, user: User = Depends(get_current_user)):
    supabase = get_supabase()
    res = (
        supabase.table("households")
        .select("*")
        .eq("invite_code", body.invite_code.upper())
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Invalid invite code.")

    household = res.data[0]
    supabase.table("users").update({"household_id": household["id"]}).eq(
        "id", user.id
    ).execute()

    return Household(**household)


# --------------------------------------------------------------------------- #
# Meals
# --------------------------------------------------------------------------- #
@app.get("/meals", response_model=list[Meal])
def list_meals(user: User = Depends(get_current_user)):
    supabase = get_supabase()
    res = supabase.table("meals").select("*").execute()
    return [Meal(**m) for m in res.data]


# --------------------------------------------------------------------------- #
# Swipes
# --------------------------------------------------------------------------- #
@app.post("/swipes", response_model=SwipeResponse)
def create_swipe(body: SwipeCreate, user: User = Depends(get_current_user)):
    supabase = get_supabase()
    household_id = require_household(user)

    # Record (or update) this user's swipe. One swipe per user/meal.
    res = (
        supabase.table("swipes")
        .upsert(
            {
                "user_id": user.id,
                "household_id": household_id,
                "meal_id": body.meal_id,
                "liked": body.liked,
            },
            on_conflict="user_id,meal_id",
        )
        .execute()
    )
    swipe = Swipe(**res.data[0])

    matched = False
    match_obj = None
    if body.liked:
        matched, match_obj = _check_for_match(household_id, body.meal_id)

    return SwipeResponse(swipe=swipe, matched=matched, match=match_obj)


def _check_for_match(household_id: str, meal_id: str):
    """A match exists when every member of the household liked the meal."""
    supabase = get_supabase()

    members = (
        supabase.table("users")
        .select("id")
        .eq("household_id", household_id)
        .execute()
    )
    member_ids = {m["id"] for m in members.data}
    if not member_ids:
        return False, None

    likes = (
        supabase.table("swipes")
        .select("user_id")
        .eq("household_id", household_id)
        .eq("meal_id", meal_id)
        .eq("liked", True)
        .execute()
    )
    liked_ids = {s["user_id"] for s in likes.data}

    if not member_ids.issubset(liked_ids):
        return False, None

    # Everyone liked it — record the match if it isn't already there.
    existing = (
        supabase.table("matches")
        .select("*")
        .eq("household_id", household_id)
        .eq("meal_id", meal_id)
        .execute()
    )
    if existing.data:
        return True, Match(**existing.data[0])

    created = (
        supabase.table("matches")
        .insert({"household_id": household_id, "meal_id": meal_id})
        .execute()
    )
    return True, Match(**created.data[0])


# --------------------------------------------------------------------------- #
# Matches
# --------------------------------------------------------------------------- #
@app.get("/matches", response_model=list[Match])
def list_matches(user: User = Depends(get_current_user)):
    supabase = get_supabase()
    household_id = require_household(user)
    res = (
        supabase.table("matches")
        .select("*")
        .eq("household_id", household_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [Match(**m) for m in res.data]


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
