"""Pydantic schemas for Mixed Plate."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    user: "User"


# ---------- User ----------
class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    household_id: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------- Household ----------
class HouseholdCreate(BaseModel):
    name: str


class HouseholdJoin(BaseModel):
    invite_code: str


class Household(BaseModel):
    id: str
    name: str
    invite_code: str
    created_by: str
    created_at: Optional[datetime] = None


# ---------- Meal ----------
class Meal(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    cuisine: Optional[str] = None
    image_url: Optional[str] = None


# ---------- Swipe ----------
class SwipeCreate(BaseModel):
    meal_id: str
    liked: bool


class Swipe(BaseModel):
    id: str
    user_id: str
    household_id: str
    meal_id: str
    liked: bool
    created_at: Optional[datetime] = None


class SwipeResponse(BaseModel):
    swipe: Swipe
    matched: bool
    match: Optional["Match"] = None


# ---------- Match ----------
class Match(BaseModel):
    id: str
    household_id: str
    meal_id: str
    created_at: Optional[datetime] = None


# Resolve forward references.
AuthResponse.model_rebuild()
SwipeResponse.model_rebuild()
