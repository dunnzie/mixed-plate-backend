"""Mixed Plate — FastAPI backend.

A household meal-matching app: members swipe on meals, and when everyone in a
household likes the same meal it becomes a "match".

Run locally:
    python3 main.py
Then check health:
    curl http://localhost:8000/health
"""
import secrets

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import database as db
from models import (
    AuthResponse,
    HealthResponse,
    Household,
    HouseholdCreate,
    HouseholdJoin,
    InviteCodeResponse,
    LoginRequest,
    Match,
    Meal,
    MessageResponse,
    PreferencesUpdate,
    SignupRequest,
    Swipe,
    SwipeCreate,
    SwipeResponse,
    User,
    UserPreferences,
)

app = FastAPI(title="Mixed Plate", version="1.0.0")

# CORS — open for the Flutter client (web/mobile).
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
def _bearer_token(authorization: str) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return authorization.split(" ", 1)[1]


def get_current_user(authorization: str = Header(...)) -> User:
    """Resolve the current user from a Bearer access token."""
    token = _bearer_token(authorization)
    supabase = db.get_supabase()

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

    profile = db.get_user(auth_user.user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return User(**profile)


def require_household(user: User) -> str:
    """Return the user's household id or raise if they have not joined one."""
    if not user.household_id:
        raise HTTPException(
            status_code=400,
            detail="You must create or join a household first.",
        )
    return user.household_id


# --------------------------------------------------------------------------- #
# 1. Health
# --------------------------------------------------------------------------- #
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        app="Mixed Plate",
        supabase_configured=db.credentials_configured(),
    )


@app.get("/")
def root():
    return {"app": "Mixed Plate", "status": "ok", "docs": "/docs"}


# --------------------------------------------------------------------------- #
# 2-4. Auth
# --------------------------------------------------------------------------- #
@app.post("/auth/signup", response_model=AuthResponse)
def signup(body: SignupRequest):
    supabase = db.get_supabase()
    try:
        res = supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if res.user is None:
        raise HTTPException(status_code=400, detail="Signup failed.")

    profile = db.create_user(res.user.id, body.email, body.name)

    if res.session is None:
        raise HTTPException(
            status_code=202,
            detail="Signup succeeded but email confirmation is required.",
        )

    return AuthResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user=User(**profile),
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    supabase = db.get_supabase()
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if res.user is None or res.session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    profile = db.get_user(res.user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found.")

    return AuthResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user=User(**profile),
    )


@app.post("/auth/logout", response_model=MessageResponse)
def logout(authorization: str = Header(...)):
    token = _bearer_token(authorization)
    supabase = db.get_supabase()
    try:
        supabase.auth.admin.sign_out(token)
    except Exception:
        # Even if the provider call fails, the client should drop the token.
        pass
    return MessageResponse(message="Logged out.")


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@app.get("/users/me", response_model=User)
def get_me(user: User = Depends(get_current_user)):
    return user


@app.get("/users/preferences", response_model=UserPreferences)
def get_preferences(user: User = Depends(get_current_user)):
    prefs = db.get_user_preferences(user.id)
    if not prefs:
        # No row yet — return sensible empty defaults rather than 404.
        return UserPreferences(user_id=user.id)
    return UserPreferences(**prefs)


@app.put("/users/preferences", response_model=UserPreferences)
def update_preferences(
    body: PreferencesUpdate, user: User = Depends(get_current_user)
):
    prefs = db.upsert_user_preferences(
        user.id, body.dietary_restrictions, body.favorite_cuisines
    )
    return UserPreferences(**prefs)


# --------------------------------------------------------------------------- #
# 5-7. Households
# --------------------------------------------------------------------------- #
@app.post("/households", response_model=Household)
def create_household(body: HouseholdCreate, user: User = Depends(get_current_user)):
    invite_code = secrets.token_hex(4).upper()  # 8-char shareable code
    household = db.create_household(body.name, invite_code, user.id)
    db.set_user_household(user.id, household["id"])  # creator auto-joins
    return Household(**household)


@app.post("/households/join", response_model=Household)
def join_household(body: HouseholdJoin, user: User = Depends(get_current_user)):
    household = db.get_household_by_invite_code(body.invite_code.upper())
    if not household:
        raise HTTPException(status_code=404, detail="Invalid invite code.")
    db.set_user_household(user.id, household["id"])
    return Household(**household)


@app.get("/households/invite-code", response_model=InviteCodeResponse)
def get_invite_code(user: User = Depends(get_current_user)):
    household_id = require_household(user)
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found.")
    return InviteCodeResponse(
        household_id=household["id"], invite_code=household["invite_code"]
    )


# --------------------------------------------------------------------------- #
# 8. Meals
# --------------------------------------------------------------------------- #
@app.get("/meals", response_model=list[Meal])
def get_meals():
    # Static hardcoded catalog — no auth or Supabase required.
    return [Meal(**m) for m in db.get_meals()]


# --------------------------------------------------------------------------- #
# 9. Swipes
# --------------------------------------------------------------------------- #
@app.post("/swipes", response_model=SwipeResponse)
def create_swipe(body: SwipeCreate, user: User = Depends(get_current_user)):
    household_id = require_household(user)
    swipe = Swipe(**db.upsert_swipe(user.id, household_id, body.meal_id, body.liked))

    matched = False
    match_obj = None
    if body.liked:
        matched, match_obj = _check_for_match(household_id, body.meal_id)

    return SwipeResponse(swipe=swipe, matched=matched, match=match_obj)


def _check_for_match(household_id: str, meal_id: str):
    """A match exists when every member of the household liked the meal."""
    members = db.get_household_members(household_id)
    member_ids = {m["id"] for m in members}
    if not member_ids:
        return False, None

    liked_ids = {s["user_id"] for s in db.get_meal_likes(household_id, meal_id)}
    if not member_ids.issubset(liked_ids):
        return False, None

    existing = db.get_match(household_id, meal_id)
    if existing:
        return True, Match(**existing)
    return True, Match(**db.create_match(household_id, meal_id))


# --------------------------------------------------------------------------- #
# 10. Matches
# --------------------------------------------------------------------------- #
@app.get("/matches", response_model=list[Match])
def get_matches(user: User = Depends(get_current_user)):
    household_id = require_household(user)
    return [Match(**m) for m in db.list_matches(household_id)]


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
