"""Supabase connection for Mixed Plate."""
import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


@lru_cache
def get_supabase() -> Client:
    """Return a cached Supabase client.

    Raises a clear error if credentials are missing so the failure is obvious
    at request time rather than a confusing stack trace.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set. "
            "Copy .env.example to .env and fill in your project credentials."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)
