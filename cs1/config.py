"""Central config. Reads from Streamlit secrets first, then environment
variables (so it works both with `.streamlit/secrets.toml` and a plain `.env`).
"""
import os

try:
    import streamlit as st
    _SECRETS = dict(st.secrets) if hasattr(st, "secrets") else {}
except Exception:
    _SECRETS = {}

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get(key: str, default: str = "") -> str:
    # secrets.toml wins, then env var, then default
    if key in _SECRETS and _SECRETS[key]:
        return str(_SECRETS[key])
    return os.environ.get(key, default)


SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_ANON_KEY = _get("SUPABASE_ANON_KEY")
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

# Optional single-user auto-login: if both are set, the app signs in
# automatically (no login form). Keep these in secrets, never in git.
APP_EMAIL = _get("APP_EMAIL")
APP_PASSWORD = _get("APP_PASSWORD")

MODEL_MARKER = _get("MODEL_MARKER", "claude-haiku-4-5-20251001")
MODEL_ANALYST = _get("MODEL_ANALYST", "claude-sonnet-4-6")

# Study defaults (can be overridden per user via the profiles table)
DEFAULT_DAILY_NEW = 18


def supabase_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def anthropic_ready() -> bool:
    return bool(ANTHROPIC_API_KEY)


def autologin_ready() -> bool:
    return bool(APP_EMAIL and APP_PASSWORD)


# Which cards the plan / progress / "today's focus" are about. "exam" = exam-style
# questions only (the default — you study exam questions); "all" = the whole bank.
# Override in secrets with STUDY_SCOPE = "all" if you ever want the seed deck counted.
STUDY_SCOPE = _get("STUDY_SCOPE", "exam")


def scope_cards(cards: list) -> list:
    """Restrict the planning/progress universe to the chosen study scope."""
    if STUDY_SCOPE == "exam":
        return [c for c in cards if c.get("source") == "exam"]
    return list(cards)
