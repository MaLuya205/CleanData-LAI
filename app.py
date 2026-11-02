import os
import re
import json
import hmac
import secrets
import hashlib
from io import BytesIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# CleanData LAI — upgraded foundation
# Run: streamlit run app.py
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="CleanData LAI | Data quality workspace",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_NAME = "CleanData LAI"
USERS_FILE = os.getenv("CLEANDATA_USERS_FILE", "users.json")
SA_TZ = ZoneInfo("Africa/Johannesburg")

# Password hashing: PBKDF2-HMAC-SHA256 with a unique random salt per account.
PBKDF2_ITERATIONS = 310_000


def now_sa():
    return datetime.now(SA_TZ)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(calculated.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        st.error("The local user database could not be read. Check the users.json file.")
        return {}


def save_users(users):
    temp_file = USERS_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2)
    os.replace(temp_file, USERS_FILE)


def password_is_strong(password: str) -> bool:
    return (
        len(password) >= 10
        and re.search(r"[A-Za-z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )


# ----------------------------- Styling ------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --navy:#0b1730; --navy2:#122447; --green:#00c58a; --muted:#91a0b8; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
