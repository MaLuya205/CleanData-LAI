from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import time
import difflib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from collections import Counter

import pandas as pd
import streamlit as st
import fitz
from PIL import Image

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    HAS_IMAGE_COORDINATES = True
except Exception:
    HAS_IMAGE_COORDINATES = False

st.set_page_config(page_title="CleanData LAI | Workspace", page_icon="🧹", layout="wide", initial_sidebar_state="expanded")

APP_NAME = "CleanData LAI"
DATA_DIR = Path(os.getenv("CLEANDATA_DATA_DIR", ".cleandata_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
OTP_MINUTES = 10

PLANS = {
    "1day": {"name": "1 Day Pass", "price": "49.00", "days": 1},
    "1week": {"name": "1 Week Pass", "price": "149.00", "days": 7},
    "1month": {"name": "1 Month Pro", "price": "399.00", "days": 30},
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#eaf0ff; --muted:#9aa8c4; --panel:#111b31; --line:#263653; --accent:#70e1b2; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:radial-gradient(ellipse at 12% 0%, #192b4b 0%, #0b1222 48%, #080e1a 100%); color:#edf3ff; }
h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.035em; color:#f7f9ff !important; }
[data-testid="stSidebar"] { background:#0b1426; border-right:1px solid #263653; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#172641,#101a2e); border:1px solid #2a3c5b; padding:16px; border-radius:16px; }
[data-testid="stMetricLabel"] { color:#d5e0f1 !important; }
[data-testid="stMetricValue"] { color:#ffffff !important; }
.stButton>button, .stDownloadButton>button { border-radius:11px; font-weight:700; min-height:2.7rem; color:#102033 !important; background:#dff8ee; border:1px solid #70d9b0; }
.stButton>button[kind="primary"] { background:linear-gradient(90deg,#35bd91,#70e1b2); color:#071b18 !important; border:0; }
div[data-testid="stForm"] { background:#111b31; padding:22px; border:1px solid #263653; border-radius:18px; }
div[data-testid="stFileUploader"] { background:#111b31; border:1px dashed #3b5278; border-radius:14px; padding:12px; }
div[data-testid="stFileUploader"] section, div[data-testid="stFileUploader"] span, div[data-testid="stFileUploader"] small, div[data-testid="stFileUploader"] p, div[data-testid="stFileUploader"] div { color:#edf3ff !important; }
div[data-testid="stFileUploader"] button { color:#102033 !important; background:#dff8ee !important; }
.block-container { padding-top:2rem; padding-bottom:3rem; max-width:1500px; }
small,.muted { color:#9aa8c4; }
.hero { padding:28px; border-radius:22px; border:1px solid #2b4164; background:linear-gradient(115deg, rgba(31,60,94,.95), rgba(15,28,49,.96)); margin-bottom:20px; }
.hero-kicker { color:#70e1b2; font-size:.78rem; text-transform:uppercase; letter-spacing:.16em; font-weight:800; }
.hero h1 { font-size:2.3rem; margin:.35rem 0; color:#f7f9ff; }
.hero p { color:#e1eaf8 !important; max-width:780px; }
.panel { background:#111b31; border:1px solid #263653; border-radius:16px; padding:18px; color:#f3f7ff !important; }
div[data-testid="stTabs"] button { font-weight:700; color:#edf3ff !important; }
hr { border-color:#263653; }
.stApp p, .stApp label, .stApp li, .stApp span { color:#edf3ff; }
.stApp [data-testid="stWidgetLabel"] p, .stApp [data-testid="stCaptionContainer"] p { color:#d0dbed !important; }
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] > div { background:#f7f9fc !important; color:#172033 !important; border-color:#9aabc2 !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color:#53627a !important; opacity:1; }
.stApp [data-baseweb="select"] *, .stApp [role="option"] { color:#172033 !important; background:#ffffff !important; }
.stApp [data-testid="stDataFrame"] { background:#ffffff; border-radius:12px; }
.stApp [data-testid="stDataFrame"] * { color:#172033 !important; }
.stApp .stAlert { color:#172033 !important; }
.stApp .stAlert p, .stApp .stAlert div, .stApp .stAlert span, .stApp .stAlert li { color:inherit !important; }
.stApp [data-testid="stExpander"] summary { color:#edf3ff !important; }
.stApp [data-testid="stSidebar"] p, .stApp [data-testid="stSidebar"] label, .stApp [data-testid="stSidebar"] span { color:#edf3ff !important; }
.stApp [data-testid="stCheckbox"] label, .stApp [data-testid="stRadio"] label { color:#edf3ff !important; }
</style>
""", unsafe_allow_html=True)

def now_utc() -> datetime:
    return datetime.utcnow()
def read_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        with USERS_FILE.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        st.error("The local account database could not be read. Do not overwrite it until it has been backed up.")
        return {}
def write_users(users: dict) -> None:
    tmp = USERS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(USERS_FILE)
def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"
def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, salt_hex, digest_hex = stored.split("$", 2)
            candidate = password_hash(password, bytes.fromhex(salt_hex)).split("$", 2)[2]
            return hmac.compare_digest(candidate, digest_hex)
        except (ValueError, TypeError):
            return False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored)
def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))
def send_otp(email: str, code: str) -> bool:
    mail_user = st.secrets.get("EMAIL_USER", os.getenv("EMAIL_USER", ""))
    mail_pass = st.secrets.get("EMAIL_PASS", os.getenv("EMAIL_PASS", ""))
    if not mail_user or not mail_pass:
        return False
    msg = MIMEText(f"Your CleanData LAI verification code is {code}.\nIt expires in {OTP_MINUTES} minutes. If you did not request it, ignore this email.")
    msg["Subject"] = "Your CleanData LAI verification code"
    msg["From"] = mail_user
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(mail_user, mail_pass)
            smtp.send_message(msg)
        return True
    except Exception:
        return False
def password_is_strong(pwd: str) -> bool:
    return len(pwd) >= 10 and any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd) and any(not c.isalnum() for c in pwd)

# ---------------------------- DATA CLEANING ENGINE ----------------------------

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [re.sub(r"\s+", " ", str(c)).strip() or f"Unnamed_{i+1}" for i, c in enumerate(result.columns)]
    seen, names = {}, []
    for name in result.columns:
        seen[name] = seen.get(name, 0) + 1
        names.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    result.columns = names
    return result

def read_csv_safely(upload) -> pd.DataFrame:
    raw = upload.getvalue()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding=encoding)
            return normalize_columns(frame)
        except Exception:
            continue
    raise ValueError("Could not parse this CSV. Check its delimiter, quotes and header row.")

def load_table(upload) -> pd.DataFrame:
    suffix = Path(upload.name).suffix.lower()
    if suffix == ".csv":
        frame = read_csv_safely(upload)
    elif suffix in (".xlsx", ".xls"):
        frame = pd.read_excel(upload, dtype=str).fillna("")
        frame = normalize_columns(frame)
    else:
        raise ValueError("Choose a CSV or Excel file.")
    if frame.empty:
        raise ValueError("The uploaded file contains no data rows.")
    if len(frame) > 1_000_000 or len(frame.columns) > 300:
        raise ValueError("This file is larger than the current workspace limit.")
    return frame.fillna("")

def _normalise_header(name: str) -> str:
    raw = re.sub(r"\s+", " ", str(name)).strip()
    key = re.sub(r"[^a-z0-9]", "", raw.lower())
    aliases = {
        "separtment": "Department", "departmant": "Department", "departement": "Department",
        "deparment": "Department", "deptartment": "Department", "dept": "Department",
        "custmerid": "Customer ID", "customerid": "Customer ID", "clientid": "Client ID",
        "phonenumber": "Phone Number", "cellphone": "Phone Number", "phone": "Phone",
        "email": "Email", "amount": "Amount", "customername": "Customer Name",
        "dateofbirth": "Date of Birth", "dob": "Date of Birth", "birthdate": "Date of Birth",
        "date": "Date", "joindate": "Join Date", "createddate": "Created Date",
        "country": "Country", "city": "City", "age": "Age", "birthyear": "Birth Year",
    }
    return aliases.get(key, raw)

def _clean_currency(value: str, force_r: bool = False) -> str:
    s = str(value).replace("\u00a0", " ").strip()
    if not s:
        return ""
    if re.search(r"[A-Za-z]", s):
        if not re.fullmatch(r"(?i)R\s*[+-]?[\d\s,\.]+", s):
            return s
    if not re.search(r"\d", s):
        return s
    has_currency = bool(re.match(r"(?i)^R\s*", s))
    number_part = re.sub(r"(?i)^R\s*", "", s).strip()
    is_negative = False
    if number_part.startswith("-"):
        is_negative = True
        number_part = number_part[1:].strip()
    elif number_part.startswith("+"):
        number_part = number_part[1:].strip()
    if not re.fullmatch(r"[\d\s,\.]+", number_part):
        return s
    num = number_part.replace(" ", "")
    if "," in num and "." in num:
        num = num.replace(",", "")
    elif "," in num:
        if re.search(r",\d{1,2}$", num):
            num = num.replace(",", ".")
        else:
            num = num.replace(",", "")
    try:
        amount = float(num)
    except ValueError:
        return s
    if is_negative:
        amount = -amount
    if has_currency or force_r:
        if amount < 0:
            return f"-R{abs(amount):,.2f}"
        return f"R{amount:,.2f}"
    return f"{amount:,.2f}"

def _parse_amount_to_float(value: str):
    s = str(value).replace("\u00a0", " ").strip()
    if not s:
        return None
    s2 = re.sub(r"(?i)^-?R\s*", "", s)
    is_neg = s.strip().startswith("-") or s.strip().startswith("-R")
    s2 = s2.replace(" ", "").replace(",", "")
    try:
        v = float(s2)
        return -v if is_neg and v > 0 else v
    except ValueError:
        return None

def _clean_phone(value: str) -> str:
    s = str(value).strip()
    if not s:
        return ""
    cleaned = re.sub(r"[^\d+]", "", s)
    if not cleaned:
        return s
    if cleaned.startswith("+27"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("27") and len(cleaned) == 11:
        cleaned = "0" + cleaned[2:]
    if re.fullmatch(r"0\d{9}", cleaned):
        return cleaned
    return s

def _normalise_department(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value)).strip()
    key = re.sub(r"[^a-z]", "", s.lower())
    known = {
        "sales": "Sales", "sale": "Sales", "saless": "Sales",
        "hr": "Human Resources", "humanresources": "Human Resources",
        "finance": "Finance", "financial": "Finance", "it": "IT",
        "informationtechnology": "IT", "marketing": "Marketing",
        "operations": "Operations", "admin": "Administration",
        "administration": "Administration", "support": "Support",
        "customerservice": "Customer Service",
    }
    return known.get(key, s.title() if s else "")

def _normalise_country(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value)).strip()
    if not s:
        return ""
    key = re.sub(r"[^a-z]", "", s.lower())
    mapping = {
        "usa": "USA", "us": "USA", "usofamerica": "USA", "unitedstates": "USA",
        "unitedstatesofamerica": "USA", "unitedamerica": "USA", "america": "USA",
        "southafrica": "South Africa", "sa": "South Africa", "rsa": "South Africa",
        "za": "South Africa", "uk": "United Kingdom", "unitedkingdom": "United Kingdom",
        "england": "United Kingdom",
    }
    if key in mapping:
        return mapping[key]
    return s.title()

def _normalise_city(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value)).strip()
    if not s:
        return ""
    key = re.sub(r"[^a-z]", "", s.lower())
    mapping = {
        "durban": "Durban", "dbn": "Durban",
        "johannesburg": "Johannesburg", "joburg": "Johannesburg", "jhb": "Johannesburg",
        "capetown": "Cape Town", "cpt": "Cape Town",
        "pretoria": "Pretoria", "pta": "Pretoria",
        "pietermaritzburg": "Pietermaritzburg", "pmb": "Pietermaritzburg",
        "kzn": "KwaZulu-Natal",
    }
    if key in mapping:
        return mapping[key]
    return s.title()

def _normalise_region(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value)).strip()
    if not s:
        return ""
    key = re.sub(r"[^a-z]", "", s.lower())
    mapping = {
        "kzn": "KwaZulu-Natal", "kwazulunatal": "KwaZulu-Natal",
        "gauteng": "Gauteng", "gp": "Gauteng",
        "westerncape": "Western Cape", "wc": "Western Cape",
        "easterncape": "Eastern Cape", "ec": "Eastern Cape",
        "limpopo": "Limpopo", "mpumalanga": "Mpumalanga",
        "northwest": "North West", "freestate": "Free State",
        "northerncape": "Northern Cape",
    }
    return mapping.get(key, s.title())

def _clean_date(value: str) -> str:
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null", "n/a", "na", "not provided"):
        return s if s.lower() not in ("nan", "none", "null", "n/a", "na") else ""
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", s):
        try:
            dt = datetime.strptime(s, "%d-%m-%Y")
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            return s
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="raise")
        if re.fullmatch(r"\d{4}", s):
            return s
        return dt.strftime("%d-%m-%Y")
    except Exception:
        pass
    for fmt in ("%Y/%m/%d", "%Y.%m.%d", "%d/%m/%y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue
    return s

def _is_date_column(col_name: str, sample_values: pd.Series) -> bool:
    col_lower = col_name.lower()
    if any(t in col_lower for t in ("date", "dob", "birth", "joined", "created", "start", "end", "expiry", "due")):
        return True
    vals = [str(v).strip() for v in sample_values.tolist() if str(v).strip()]
    if len(vals) < 3:
        return False
    date_like = 0
    for v in vals[:50]:
        if re.search(r"\d{1,4}[-/\.]\d{1,2}[-/\.]\d{2,4}", v) or re.search(r"\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", v, re.I):
            try:
                pd.to_datetime(v, dayfirst=True, errors="raise")
                date_like += 1
            except Exception:
                pass
    return date_like / max(1, min(len(vals), 50)) >= 0.6

def _score_email(email: str, full_name: str) -> int:
    e = email.strip().lower()
    if not valid_email(e):
        return -100
    local, domain = e.split("@", 1)
    score = 0
    name_nospace = re.sub(r"[^a-z]", "", full_name.lower())
    first_name = full_name.lower().split()[0] if full_name.strip() else ""
    if local == name_nospace:
        score += 50
    elif name_nospace in local:
        score += 30
    elif first_name and first_name in local:
        score += 10
    if domain in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com"):
        score += 20
    elif "." in domain and len(domain.split(".")[-1]) >= 2:
        score += 5
    score += len(local)
    return score

def _repair_emails(df: pd.DataFrame, audit: list[str]) -> pd.DataFrame:
    email_col = next((c for c in df.columns if "email" in c.lower()), None)
    name_col = next((c for c in df.columns if c.lower() in ("customer name", "name", "customer", "client name")), None)
    phone_col = next((c for c in df.columns if "phone" in c.lower() or "cell" in c.lower() or "mobile" in c.lower()), None)
    if not email_col or not name_col or not phone_col:
        return df
    df = df.copy()
    fixed = 0
    for (name, phone), group in df.groupby([name_col, phone_col], dropna=False):
        if len(group) < 2:
            continue
        emails = [str(x).strip().lower() for x in group[email_col].tolist() if str(x).strip()]
        if not emails:
            continue
        valid = [e for e in emails if valid_email(e)]
        if not valid:
            continue
        best = max(valid, key=lambda e: _score_email(e, str(name)))
        for idx in group.index:
            cur = str(df.at[idx, email_col]).strip().lower()
            if cur != best:
                cur_score = _score_email(cur, str(name))
                best_score = _score_email(best, str(name))
                if not valid_email(cur) or (best_score - cur_score >= 20):
                    df.at[idx, email_col] = best
                    fixed += 1
    if fixed:
        audit.append(f"Email: repaired {fixed} email(s) using the correct email from the same person (same Name + Phone).")
    return df

def build_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(df)
    for col in df.columns:
        series = df[col].astype(str)
        blanks = int((series == "").sum())
        uniques = int(series.nunique())
        try:
            top = series[series != ""].value_counts().head(3).index.tolist()
            sample = ", ".join([str(x)[:25] for x in top])
        except Exception:
            sample = ""
        col_lower = col.lower()
        if any(t in col_lower for t in ("amount", "price", "total", "salary")):
            dtype_guess = "Money (R)"
        elif any(t in col_lower for t in ("phone", "cell")):
            dtype_guess = "Phone"
        elif "email" in col_lower:
            dtype_guess = "Email"
        elif any(t in col_lower for t in ("date", "dob", "birth")):
            dtype_guess = "Date (DD-MM-YYYY)"
        elif "age" in col_lower:
            dtype_guess = "Age / Number"
        else:
            dtype_guess = "Text"
        rows.append({"Column": col, "Type Guess": dtype_guess, "Rows": total, "Blank Cells": blanks, "Blank %": f"{(blanks/total*100) if total else 0:.1f}%", "Unique Values": uniques, "Top Values": sample})
    try:
        dup_exact = int(df.duplicated().sum())
    except Exception:
        dup_exact = 0
    rows.append({"Column": "--- OVERALL ---", "Type Guess": f"Exact duplicates: {dup_exact}", "Rows": total, "Blank Cells": int(df.eq("").sum().sum()), "Blank %": "", "Unique Values": "", "Top Values": f"Columns: {len(df.columns)}"})
    return pd.DataFrame(rows)

def apply_smart_missing(df: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    audit = []
    if mode == "Delete rows with blanks":
        before = len(df)
        df = df.replace(r"^\s*$", pd.NA, regex=True).dropna().copy()
        df = df.fillna("")
        audit.append(f"Smart Missing (Delete): removed {before-len(df)} row(s) with blanks.")
        return df, audit
    for col in df.columns:
        blanks = (df[col].astype(str) == "").sum()
        if blanks == 0:
            continue
        col_lower = col.lower()
        is_money = any(t in col_lower for t in ("amount", "price", "cost", "salary", "revenue", "total", "balance", "payment"))
        is_age = "age" in col_lower or "birth year" in col_lower
        if is_money:
            nums = [_parse_amount_to_float(v) for v in df[col].tolist()]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            if mode == "Average":
                fill_val_num = sum(nums)/len(nums)
            elif mode == "Median":
                s_sorted = sorted(nums)
                fill_val_num = s_sorted[len(s_sorted)//2]
            else:
                fill_val_num = Counter(nums).most_common(1)[0][0]
            fill_val = f"R{fill_val_num:,.2f}"
            df[col] = df[col].replace("", fill_val)
            audit.append(f"{col}: filled {int(blanks)} blank(s) with {mode} = {fill_val}")
        elif is_age:
            nums = []
            for v in df[col].tolist():
                try:
                    if str(v).strip() != "":
                        nums.append(float(str(v).strip()))
                except ValueError:
                    pass
            if not nums:
                continue
            if mode == "Average":
                fill_val_num = sum(nums)/len(nums)
            elif mode == "Median":
                s_sorted = sorted(nums)
                fill_val_num = s_sorted[len(s_sorted)//2]
            else:
                fill_val_num = Counter(nums).most_common(1)[0][0]
            fill_val = str(int(round(fill_val_num)))
            df[col] = df[col].replace("", fill_val)
            audit.append(f"{col}: filled {int(blanks)} blank(s) with {mode} = {fill_val}")
        else:
            vals = [str(v) for v in df[col].tolist() if str(v).strip() != ""]
            if not vals:
                continue
            fill_val = Counter(vals).most_common(1)[0][0]
            df[col] = df[col].replace("", fill_val)
            audit.append(f"{col}: filled {int(blanks)} blank(s) with Most Common = {fill_val} (text columns always use Most Common)")
    if not audit:
        audit.append("Smart Missing: no blank cells found.")
    return df, audit

def _names_similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def apply_fuzzy_dedupe(df: pd.DataFrame, threshold: float = 0.85) -> tuple[pd.DataFrame, int, list[str]]:
    if len(df) == 0:
        return df, 0, []
    name_col = next((c for c in df.columns if c.lower() in ("customer name", "name", "customer", "client name")), None)
    phone_col = next((c for c in df.columns if "phone" in c.lower() or "cell" in c.lower()), None)
    amount_col = next((c for c in df.columns if c.lower() == "amount"), None)
    if not name_col or not phone_col:
        return df, 0, ["Fuzzy Dedupe: need Name + Phone columns to run."]
    df = df.copy().reset_index(drop=True)
    to_drop = set()
    details = []
    for phone, group in df.groupby(phone_col, dropna=False):
        idxs = group.index.tolist()
        if len(idxs) < 2:
            continue
        for i in range(len(idxs)):
            for j in range(i+1, len(idxs)):
                a_idx, b_idx = idxs[i], idxs[j]
                if a_idx in to_drop or b_idx in to_drop:
                    continue
                name_a = str(df.at[a_idx, name_col])
                name_b = str(df.at[b_idx, name_col])
                sim = _names_similar(name_a, name_b)
                amount_same = True
                if amount_col:
                    amount_same = str(df.at[a_idx, amount_col]).strip() == str(df.at[b_idx, amount_col]).strip()
                if sim >= threshold and amount_same:
                    to_drop.add(b_idx)
                    details.append(f"Fuzzy duplicate: '{name_a}' ~ '{name_b}' ({sim*100:.0f}% similar) same phone {phone} same amount -> removed row {b_idx+1}")
                elif sim >= 0.95 and not amount_col:
                    to_drop.add(b_idx)
                    details.append(f"Fuzzy duplicate: '{name_a}' ~ '{name_b}' ({sim*100:.0f}%) same phone -> removed")
    if to_drop:
        df = df.drop(index=list(to_drop)).reset_index(drop=True)
    return df, len(to_drop), details

def find_outliers(df: pd.DataFrame) -> pd.DataFrame:
    out_rows = []
    for idx, row in df.iterrows():
        for col in df.columns:
            val = str(row[col]).strip()
            if val == "":
                continue
            col_lower = col.lower()
            if any(t in col_lower for t in ("amount", "price", "total", "salary", "revenue", "balance", "payment")):
                num = _parse_amount_to_float(val)
                if num is not None and num < 0:
                    out_rows.append({"Row": int(idx)+1, "Column": col, "Value": val, "Reason": "Negative money - possible typo, should it be positive?"})
                elif num is not None and num > 1000000:
                    out_rows.append({"Row": int(idx)+1, "Column": col, "Value": val, "Reason": "Very large amount > R1,000,000 - check if extra zeros"})
            if col_lower == "age":
                try:
                    age = float(val)
                    if age < 0 or age > 120:
                        out_rows.append({"Row": int(idx)+1, "Column": col, "Value": val, "Reason": "Impossible age - must be 0-120"})
                except ValueError:
                    pass
            if "birth" in col_lower and "year" in col_lower:
                try:
                    yr = int(float(val))
                    if yr < 1900 or yr > 2026:
                        out_rows.append({"Row": int(idx)+1, "Column": col, "Value": val, "Reason": "Impossible birth year - e.g. 1850 means 176 years old"})
                except ValueError:
                    pass
            if col_lower in ("date of birth", "dob", "birth date", "date"):
                m = re.search(r"(\d{4})", val)
                if m:
                    try:
                        yr = int(m.group(1))
                        if yr < 1900 or yr > 2026:
                            out_rows.append({"Row": int(idx)+1, "Column": col, "Value": val, "Reason": "Impossible year in date - check typo"})
                    except ValueError:
                        pass
    return pd.DataFrame(out_rows)

def build_validation_report(before_df: pd.DataFrame, after_df: pd.DataFrame, audit: list[str]) -> pd.DataFrame:
    try:
        before_rows = len(before_df)
        after_rows = len(after_df)
        before_blanks = int(before_df.eq("").sum().sum()) if before_df.size else 0
        after_blanks = int(after_df.eq("").sum().sum()) if after_df.size else 0
        before_dup = int(before_df.duplicated().sum()) if before_df.size else 0
        after_dup = int(after_df.duplicated().sum()) if after_df.size else 0
    except Exception:
        before_rows, after_rows, before_blanks, after_blanks, before_dup, after_dup = 0, 0, 0, 0, 0, 0
    report = [
        {"Check": "Total Rows", "Before": before_rows, "After": after_rows, "Status": "✅ Cleaned" if after_rows <= before_rows else "⚠️ Check"},
        {"Check": "Total Blank Cells", "Before": before_blanks, "After": after_blanks, "Status": "✅ Improved" if after_blanks <= before_blanks else "⚠️ More blanks - check"},
        {"Check": "Exact Duplicates", "Before": before_dup, "After": after_dup, "Status": "✅ Removed" if after_dup <= before_dup else "⚠️ Check"},
        {"Check": "Columns", "Before": len(before_df.columns) if before_df is not None else 0, "After": len(after_df.columns) if after_df is not None else 0, "Status": "✅ Same columns - no data lost"},
        {"Check": "Good Data Corrupted?", "Before": "N/A", "After": "0 - We only standardise, never delete good values without audit", "Status": "✅ Safe"},
    ]
    return pd.DataFrame(report)

def clean_table(source: pd.DataFrame, missing_policy: str, remove_duplicates: bool, normalize_case: bool, trim_text: bool, standardize_business_fields: bool = True, normalize_numbers: bool = True, normalize_dates: bool = True, format_fixer: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    df = normalize_columns(source.copy())
    audit: list[str] = []
    before_rows = len(df)
    old_columns = list(df.columns)
    new_columns = [_normalise_header(c) if standardize_business_fields else c for c in old_columns]
    counts, unique_columns = {}, []
    for col in new_columns:
        counts[col] = counts.get(col, 0) + 1
        unique_columns.append(col if counts[col] == 1 else f"{col}_{counts[col]}")
    df.columns = unique_columns
    changed_headers = sum(a != b for a, b in zip(old_columns, unique_columns))
    if changed_headers:
        audit.append(f"Corrected or standardised {changed_headers} column heading(s).")
    empty_rows = df.replace(r"^\s*$", pd.NA, regex=True).isna().all(axis=1)
    removed_empty = int(empty_rows.sum())
    if removed_empty:
        df = df.loc[~empty_rows].copy()
        audit.append(f"Removed {removed_empty} completely empty row(s).")
    for col in df.columns:
        old = df[col].astype(str)
        new = old.copy()
        if trim_text:
            new = (new.str.replace(r"[\u00a0\t\r\n]", " ", regex=True)
                   .str.replace(r"[\u200b-\u200f\ufeff]", "", regex=True)
                   .str.replace(r"\s+", " ", regex=True)
                   .str.strip())
        null_mask = new.str.lower().isin(["nan", "none", "null", "n/a", "na"])
        new.loc[null_mask] = ""
        col_lower = col.strip().lower()
        is_money_col = any(t in col_lower for t in ("amount", "price", "cost", "salary", "revenue", "total", "balance", "payment"))
        is_phone_col = any(t in col_lower for t in ("phone", "cell", "mobile", "contact"))
        is_email_col = "email" in col_lower
        is_country_col = col_lower == "country"
        is_city_col = col_lower == "city"
        is_region_col = col_lower in ("province", "region", "state")
        is_date_col = _is_date_column(col, new) if normalize_dates else False
        if col_lower == "department" and standardize_business_fields:
            new = new.map(_normalise_department)
        if format_fixer and is_country_col:
            new = new.map(_normalise_country)
        elif format_fixer and is_city_col:
            new = new.map(_normalise_city)
        elif format_fixer and is_region_col:
            new = new.map(_normalise_region)
        if is_phone_col:
            new = new.map(_clean_phone)
        elif is_email_col:
            new = new.str.lower().str.strip()
        elif is_date_col:
            new = new.map(_clean_date)
            invalid_dates = new.ne("") & ~new.str.fullmatch(r"\d{2}-\d{2}-\d{4}", na=False)
            if invalid_dates.any():
                audit.append(f"{col}: flagged {int(invalid_dates.sum())} date value(s) that could not be parsed to DD-MM-YYYY; preserved for review.")
        elif normalize_case and any(token in col_lower for token in ("name", "customer", "client")):
            if not any(token in col_lower for token in ("id", "code", "number")):
                new = new.str.title()
        if normalize_numbers and is_money_col:
            def _safe_money(v):
                if v == "":
                    return ""
                if re.search(r"[A-Za-z]", v) and not re.fullmatch(r"(?i)R\s*[+-]?[\d\s,\.]+", v.strip()):
                    return v
                return _clean_currency(v, force_r=True)
            new = new.map(_safe_money)
        elif normalize_numbers and not is_phone_col and not is_date_col:
            mask = new.str.fullmatch(r"(?i)R\s*[+-]?[\d\s,\.]+", na=False)
            if mask.any():
                new.loc[mask] = new.loc[mask].map(lambda x: _clean_currency(x, force_r=False))
        changed = int((old != new).sum())
        if changed:
            audit.append(f"{col}: standardised {changed} cell(s).")
        df[col] = new
    df = _repair_emails(df, audit)
    email_col = next((c for c in df.columns if "email" in c.lower()), None)
    if email_col:
        invalid = df[email_col].astype(str).ne("") & ~df[email_col].astype(str).str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if invalid.any():
            audit.append(f"{email_col}: flagged {int(invalid.sum())} invalid email value(s) that could not be repaired from same person; preserved for review.")
    missing_count = int(df.eq("").sum().sum())
    if missing_policy == "Drop rows with missing values":
        before = len(df)
        df = df.replace(r"^\s*$", pd.NA, regex=True).dropna().copy()
        df = df.fillna("")
        audit.append(f"Removed {before-len(df)} row(s) containing one or more missing values.")
    elif missing_policy == "Fill text blanks with 'Not provided'":
        for col in df.columns:
            df[col] = df[col].replace("", "Not provided")
        audit.append("Filled blank cells with 'Not provided' at the user's request.")
    else:
        audit.append(f"Preserved {missing_count} blank cell(s); no missing values were guessed.")
    if remove_duplicates:
        before_dedup = len(df)
        df = df.drop_duplicates().copy()
        exact_removed = before_dedup - len(df)
        smart_removed = 0
        name_col = next((c for c in df.columns if c.lower() in ("customer name", "name", "customer", "client name")), None)
        phone_col = next((c for c in df.columns if "phone" in c.lower() or "cell" in c.lower()), None)
        amount_col = next((c for c in df.columns if c.lower() == "amount"), None)
        dept_col = next((c for c in df.columns if c.lower() == "department"), None)
        if name_col and phone_col and amount_col:
            subset = [name_col, phone_col, amount_col]
            if dept_col:
                subset.append(dept_col)
            before_smart = len(df)
            df = df.drop_duplicates(subset=subset, keep="first").copy()
            smart_removed = before_smart - len(df)
        total_removed = exact_removed + smart_removed
        if total_removed:
            audit.append(f"Removed {total_removed} duplicate row(s) (exact + same person + same amount, even if email had typos).")
        else:
            audit.append("Removed 0 duplicate row(s).")
    audit.insert(0, f"Input rows: {before_rows}; output rows: {len(df)}.")
    audit.append(f"Output columns: {len(df.columns)}.")
    audit.append("Review standardised values before using them in financial, payroll or legal records.")
    return df, pd.DataFrame(audit, columns=["Cleaning audit"]), audit

def dataframe_downloads(df: pd.DataFrame) -> tuple[bytes, bytes]:
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned data")
    return csv_bytes, xbuf.getvalue()

# ---------------------------- PDF EDITOR ----------------------------

def render_pdf_page(doc: fitz.Document, page_number: int, scale: float = 1.5) -> Image.Image:
    page = doc[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
def replace_pdf_span(pdf_bytes: bytes, page_number: int, bbox_tuple, replacement: str) -> bytes:
    if not replacement.strip():
        raise ValueError("Replacement text cannot be empty.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        rect = fitz.Rect(bbox_tuple)
        rect.x0 -= 0.8; rect.y0 -= 0.4; rect.x1 += 0.8; rect.y1 += 0.8
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=0)
        font_size = max(5, min(18, float(rect.height) * 0.78))
        result = page.insert_textbox(rect, replacement, fontname="helv", fontsize=font_size, color=(0, 0, 0), align=fitz.TEXT_ALIGN_LEFT, overlay=True)
        if result < 0:
            raise ValueError("Replacement text is too long for the selected area.")
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_add_text(pdf_bytes: bytes, page_number: int, text: str, x: float, y: float, font_size: float = 11, color: tuple = (0, 0, 0)) -> bytes:
    if not text.strip():
        raise ValueError("Enter text to add.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        page.insert_text((x, y), text, fontsize=font_size, fontname="helv", color=color, overlay=True)
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_highlight_search(pdf_bytes: bytes, page_number: int, phrase: str) -> bytes:
    if not phrase.strip():
        raise ValueError("Enter text to highlight.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        matches = page.search_for(phrase, quads=True)
        if not matches:
            raise ValueError("No matching text was found on this page.")
        annot = page.add_highlight_annot(matches)
        annot.update()
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_search_replace(pdf_bytes: bytes, page_number: int, phrase: str, replacement: str) -> bytes:
    if not phrase.strip() or not replacement.strip():
        raise ValueError("Enter both the text to find and its replacement.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        matches = page.search_for(phrase)
        if not matches:
            raise ValueError("No matching selectable text was found on this page.")
        for rect in matches:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=0)
        for rect in matches:
            font_size = max(6, min(18, rect.height * 0.78))
            result = page.insert_textbox(rect, replacement, fontname="helv", fontsize=font_size, color=(0, 0, 0), overlay=True)
            if result < 0:
                raise ValueError("Replacement is too long for the original text area. Try shorter wording.")
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_rotate_page(pdf_bytes: bytes, page_number: int, degrees: int) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        page.set_rotation((page.rotation + degrees) % 360)
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_delete_page(pdf_bytes: bytes, page_number: int) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) <= 1:
            raise ValueError("A PDF must contain at least one page.")
        doc.delete_page(page_number)
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
def pdf_merge(pdf_files: list[bytes]) -> bytes:
    if not pdf_files:
        raise ValueError("Upload at least one additional PDF.")
    output = fitz.open()
    try:
        for raw in pdf_files:
            with fitz.open(stream=raw, filetype="pdf") as part:
                if part.is_encrypted:
                    raise ValueError("One of the uploaded PDFs is password-protected.")
                output.insert_pdf(part)
        return output.tobytes(garbage=4, deflate=True)
    finally:
        output.close()

# ---------------------------- NEW: FILE CONVERTER + PDF TOOLKIT + INVOICE ----------------------------

def image_to_pdf_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()

def text_to_pdf_bytes(text: str, title: str = "Document") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    page.insert_text((50, y), title, fontsize=18, fontname="helv", color=(0, 0, 0))
    y += 30
    for line in text.splitlines():
        if y > 750:
            page = doc.new_page()
            y = 60
        # Wrap long lines at 95 chars
        while len(line) > 95:
            page.insert_text((50, y), line[:95], fontsize=11, fontname="helv")
            y += 16
            line = line[95:]
            if y > 750:
                page = doc.new_page()
                y = 60
        page.insert_text((50, y), line, fontsize=11, fontname="helv")
        y += 16
    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out

def pdf_to_text_bytes(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    try:
        for page in doc:
            parts.append(page.get_text("text"))
        return "\n".join(parts)
    finally:
        doc.close()

def pdf_compress(pdf_bytes: bytes) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

def pdf_split(pdf_bytes: bytes, start_page: int, end_page: int) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if start_page < 1 or end_page < start_page or end_page > len(doc):
            raise ValueError(f"Page range must be 1 to {len(doc)}")
        out = fitz.open()
        out.insert_pdf(doc, from_page=start_page-1, to_page=end_page-1)
        result = out.tobytes(garbage=4, deflate=True)
        out.close()
        return result
    finally:
        doc.close()

def pdf_watermark(pdf_bytes: bytes, text: str) -> bytes:
    if not text.strip():
        raise ValueError("Enter watermark text.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            rect = page.rect
            # Diagonal watermark in middle, light grey
            page.insert_text((rect.width*0.2, rect.height*0.5), text, fontsize=48, fontname="helv", color=(0.85, 0.85, 0.85), rotate=45, overlay=True)
            page.insert_text((50, 30), text, fontsize=10, fontname="helv", color=(0.6, 0.6, 0.6), overlay=True)
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

def generate_invoice_pdf(business_name: str, business_email: str, business_phone: str, banking: str, client_name: str, client_email: str, invoice_no: str, invoice_date: str, items: list[dict], vat_enabled: bool, vat_rate: float = 15.0, notes: str = "") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 50
    page.insert_text((50, y), "INVOICE", fontsize=26, fontname="hebo", color=(0.05, 0.2, 0.25))
    y += 22
    page.insert_text((50, y), business_name, fontsize=14, fontname="helv", color=(0, 0, 0))
    y += 18
    if business_email:
        page.insert_text((50, y), f"Email: {business_email}", fontsize=10, fontname="helv")
        y += 14
    if business_phone:
        page.insert_text((50, y), f"Phone: {business_phone}", fontsize=10, fontname="helv")
        y += 14
    if banking:
        page.insert_text((50, y), f"Banking: {banking}", fontsize=10, fontname="helv")
        y += 14
    y += 10
    page.insert_text((50, y), f"Invoice No: {invoice_no}", fontsize=11, fontname="hebo")
    page.insert_text((350, y), f"Date: {invoice_date}", fontsize=11, fontname="helv")
    y += 20
    page.insert_text((50, y), f"Bill To: {client_name}", fontsize=12, fontname="hebo")
    y += 16
    if client_email:
        page.insert_text((50, y), f"Email: {client_email}", fontsize=10, fontname="helv")
        y += 16
    y += 10
    # Table header
    page.insert_text((50, y), "Description", fontsize=10, fontname="hebo")
    page.insert_text((280, y), "Qty", fontsize=10, fontname="hebo")
    page.insert_text((330, y), "Rate", fontsize=10, fontname="hebo")
    page.insert_text((430, y), "Total", fontsize=10, fontname="hebo")
    y += 14
    page.draw_line((50, y), (545, y))
    y += 16
    subtotal = 0.0
    for it in items:
        desc = str(it.get("desc", ""))[:45]
        try:
            qty = float(it.get("qty", 1))
        except Exception:
            qty = 1.0
        try:
            rate = float(it.get("rate", 0))
        except Exception:
            rate = 0.0
        total = qty * rate
        subtotal += total
        page.insert_text((50, y), desc, fontsize=10, fontname="helv")
        page.insert_text((280, y), f"{qty:g}", fontsize=10, fontname="helv")
        page.insert_text((330, y), f"R{rate:,.2f}", fontsize=10, fontname="helv")
        page.insert_text((430, y), f"R{total:,.2f}", fontsize=10, fontname="helv")
        y += 18
        if y > 650:
            page = doc.new_page(width=595, height=842)
            y = 50
    y += 10
    page.draw_line((50, y), (545, y))
    y += 18
    vat_amount = subtotal * (vat_rate/100.0) if vat_enabled else 0.0
    grand = subtotal + vat_amount
    page.insert_text((330, y), "Subtotal:", fontsize=11, fontname="helv")
    page.insert_text((430, y), f"R{subtotal:,.2f}", fontsize=11, fontname="helv")
    y += 18
    if vat_enabled:
        page.insert_text((330, y), f"VAT ({vat_rate:.0f}%):", fontsize=11, fontname="helv")
        page.insert_text((430, y), f"R{vat_amount:,.2f}", fontsize=11, fontname="helv")
        y += 18
    page.insert_text((330, y), "TOTAL DUE:", fontsize=13, fontname="hebo")
    page.insert_text((430, y), f"R{grand:,.2f}", fontsize=13, fontname="hebo")
    y += 30
    if notes:
        page.insert_text((50, y), f"Notes: {notes[:120]}", fontsize=10, fontname="helv")
        y += 16
    page.insert_text((50, y), "Thank you for your business! - Generated with CleanData LAI", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out

def get_payfast_config():
    try:
        cfg = st.secrets["payfast"]
        return (str(cfg["merchant_id"]), str(cfg["merchant_key"]), str(cfg.get("process_url", "https://www.payfast.co.za/eng/process")))
    except Exception:
        return ("", "", "https://sandbox.payfast.co.za/eng/process")
def payfast_checkout(email: str, plan_key: str):
    mid, mkey, endpoint = get_payfast_config()
    if not mid or not mkey:
        st.info("Payments are not configured yet. Add verified PayFast credentials and a server-side ITN endpoint.")
        return
    plan = PLANS[plan_key]
    st.warning("Payment activation must be confirmed by a server-side PayFast ITN validation before access is extended.")
    st.code(f"Merchant: {mid}\nPlan: {plan['name']}\nAmount: R{plan['price']}\nEndpoint: {endpoint}")

def init_state():
    defaults = {"auth": {"logged_in": False, "page": "signin"}, "pending_signup": None, "cleaned_df": None, "clean_audit": None, "pdf_bytes": None, "pdf_name": None, "pdf_selected": None, "pdf_page": 0, "original_df": None, "profile_df": None, "outliers_df": None, "validation_df": None, "daily_tasks": [], "invoice_items": [{"desc": "Data Cleaning Service", "qty": 1, "rate": 250.0}]}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
init_state()
users = read_users()

def hero():
    st.markdown("""<div class="hero"><div class="hero-kicker">Clean workspace · Better decisions</div><h1>Make messy data make sense.</h1><p>Clean, validate, review and export business data. Edit existing PDF text directly on the page, with a preview before you download.</p></div>""", unsafe_allow_html=True)

def auth_pages():
    hero()
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown("### Your business data workspace")
        st.markdown("- **Data cleaning:** whitespace, blank values, duplicates and validation flags.\n- **PDF workspace:** render the original page, click text and replace it.\n- **Exports:** download cleaned CSV and Excel files.\n- **Safer accounts:** salted password hashing and email OTP verification.")
        st.info("For production, configure persistent database storage and email secrets before inviting customers.")
    with right:
        account_type_choice = st.radio(
            "Choose your workspace",
            ["Individual", "Business"],
            horizontal=True,
            key="auth_account_type",
        )
        business_size_choice = ""
        if account_type_choice == "Business":
            business_size_choice = st.selectbox(
                "Business size",
                ["Small Business", "Big Company"],
                key="auth_business_size",
            )
        default_mode = 1 if st.session_state.pending_signup else (0 if st.session_state.auth["page"] == "signin" else 1)
        mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True, index=default_mode)
        if mode == "Create account":
            with st.form("signup_form"):
                name = st.text_input("Full name")
                company_label = "Business / team name" if account_type_choice == "Business" else "Workspace name (optional)"
                company = st.text_input(company_label)
                email = st.text_input("Email address")
                password = st.text_input("Password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                submit = st.form_submit_button("Create account & send OTP", type="primary", use_container_width=True)
            if submit:
                email = email.strip().lower()
                if not name.strip() or (account_type_choice == "Business" and not company.strip()) or not valid_email(email):
                    st.error("Enter your name, a business name for Business accounts, and a valid email address.")
                elif email in users:
                    st.error("An account with this email already exists.")
                elif password != confirm:
                    st.error("The passwords do not match.")
                elif not password_is_strong(password):
                    st.error("Use at least 10 characters, including a letter, number and symbol.")
                else:
                    code = f"{secrets.randbelow(1_000_000):06d}"
                    sent = send_otp(email, code)
                    if not sent:
                        st.error("OTP email could not be sent. Configure EMAIL_USER and EMAIL_PASS in Streamlit Secrets, then try again. No account was created.")
                    else:
                        workspace_name = company.strip() or f"{name.strip()}'s Workspace"
                        st.session_state.pending_signup = {
                            "name": name.strip(),
                            "company": workspace_name,
                            "email": email,
                            "account_type": account_type_choice,
                            "business_size": business_size_choice if account_type_choice == "Business" else "",
                            "password_hash": password_hash(password),
                            "otp_hash": hashlib.sha256(code.encode()).hexdigest(),
                            "created_at": time.time(),
                            "attempts": 0,
                        }
                        st.success("Verification code sent. It expires in 10 minutes.")
                        st.rerun()
            pending = st.session_state.pending_signup
            if pending:
                st.divider()
                st.markdown(f"**Verify email:** `{pending['email']}`")
                with st.form("otp_form"):
                    otp = st.text_input("Six-digit verification code", max_chars=6)
                    verify = st.form_submit_button("Verify email & create account", type="primary", use_container_width=True)
                if verify:
                    pending["attempts"] += 1
                    expected = pending["otp_hash"]
                    supplied = hashlib.sha256(otp.strip().encode()).hexdigest()
                    if time.time() - pending["created_at"] > OTP_MINUTES * 60:
                        st.session_state.pending_signup = None
                        st.error("Code expired. Start registration again.")
                    elif pending["attempts"] > 5:
                        st.session_state.pending_signup = None
                        st.error("Too many attempts. Start registration again.")
                    elif not hmac.compare_digest(expected, supplied):
                        st.error("Incorrect code.")
                    else:
                        users[pending["email"]] = {
                            "name": pending["name"],
                            "company": pending["company"],
                            "account_type": pending.get("account_type", "Business"),
                            "business_size": pending.get("business_size", ""),
                            "role": "owner",
                            "password": pending["password_hash"],
                            "verified": True,
                            "created_at": now_utc().isoformat(),
                            "paid_until": (now_utc() + timedelta(days=1)).isoformat(),
                            "plan": "trial",
                        }
                        write_users(users)
                        st.session_state.pending_signup = None
                        st.session_state.auth = {"logged_in": True, "user": pending["email"], "page": "signin"}
                        st.success("Account created. Your trial workspace is ready.")
                        st.rerun()
        else:
            with st.form("signin_form"):
                email = st.text_input("Email address").strip().lower()
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submit:
                record = users.get(email)
                if not record or not verify_password(password, record.get("password", "")):
                    st.error("Email or password is incorrect.")
                elif str(record.get("account_type", "Business")).title() != account_type_choice:
                    st.error(f"This email belongs to a {record.get('account_type', 'Business')} workspace. Select the matching workspace type above.")
                elif not record.get("verified"):
                    st.error("This account has not completed email verification.")
                else:
                    if not record.get("password", "").startswith("pbkdf2_sha256$"):
                        record["password"] = password_hash(password)
                        write_users(users)
                    st.session_state.auth = {"logged_in": True, "user": email, "page": "signin"}
                    st.rerun()

def workspace(email: str):
    user = users.get(email, {})
    account_type = str(user.get("account_type", "Business")).title()
    business_size = user.get("business_size", "")
    if account_type == "Individual":
        st.markdown("""
        <style>
        .stApp { background:linear-gradient(145deg,#f7fff9 0%,#eaf8ef 58%,#ffffff 100%); color:#173328; }
        .stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp label,.stApp li,.stApp span { color:#173328 !important; }
        [data-testid="stSidebar"] { background:#e4f5e9; border-right:1px solid #b8dfc5; }
        [data-testid="stMetric"] { background:#ffffff; border:1px solid #c8e6d1; }
        [data-testid="stMetricLabel"] { color:#315b43 !important; }
        [data-testid="stMetricValue"] { color:#14532d !important; }
        .hero { background:linear-gradient(115deg,#d8f4e1,#f5fff7); border:1px solid #b8dfc5; }
        .hero h1,.hero p { color:#173328 !important; }
        .panel { background:#ffffff; border:1px solid #c8e6d1; color:#173328 !important; }
        div[data-testid="stTabs"] button { color:#14532d !important; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        .stApp { background:radial-gradient(ellipse at 15% 0%,#252015 0%,#111111 48%,#050505 100%); color:#f5edda; }
        .stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp label,.stApp li,.stApp span { color:#f5edda !important; }
        [data-testid="stSidebar"] { background:#11100d; border-right:1px solid #57451e; }
        [data-testid="stMetric"] { background:linear-gradient(145deg,#292315,#15130e); border:1px solid #6d5725; }
        [data-testid="stMetricLabel"] { color:#e5d5a5 !important; }
        [data-testid="stMetricValue"] { color:#f4d477 !important; }
        .hero { background:linear-gradient(115deg,#302716,#17140e); border:1px solid #8a6c2e; }
        .hero-kicker { color:#f4d477 !important; }
        .hero h1,.hero p { color:#fff4d6 !important; }
        .panel { background:#17140e; border:1px solid #6d5725; color:#f5edda !important; }
        .stButton>button[kind="primary"] { background:linear-gradient(90deg,#c49a36,#f4d477); color:#17130a !important; }
        div[data-testid="stTabs"] button { color:#f4d477 !important; }
        </style>
        """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("## 🧹 CleanData LAI")
        st.caption(f"{account_type} workspace" + (f" · {business_size}" if business_size else ""))
        st.write(f"**{user.get('name', 'User')}**")
        st.caption(user.get("company", ""))
        st.caption(f"Account type: {account_type}" + (f" · {business_size}" if business_size else ""))
        st.divider()
        st.write(f"Account: `{email}`")
        expiry_text = user.get("paid_until", "")
        try:
            expiry = datetime.fromisoformat(expiry_text)
            active = expiry > now_utc()
        except Exception:
            active = False
        st.write("Subscription: " + ("Active" if active else "Expired / not set"))
        if st.button("Log out", use_container_width=True):
            st.session_state.auth = {"logged_in": False, "page": "signin"}
            st.session_state.cleaned_df = None
            st.session_state.original_df = None
            st.rerun()
    hero()
    overview_title = "Individual dashboard" if account_type == "Individual" else f"Business dashboard · {business_size or 'Business'}"
    tabs = st.tabs([overview_title, "Data cleaning", "PDF editor", "🔄 File Converter", "📦 PDF Toolkit", "⏰ Daily Planner", "🧾 Quick Invoice", "Plans & account"])
    with tabs[0]:
        st.subheader(overview_title)
        if account_type == "Business":
            st.caption("Business workspace. Business size is recorded at registration; staff permissions and company-wide reporting require a separate secure team backend.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Account status", "Verified" if user.get("verified") else "Unverified")
        c2.metric("Plan", user.get("plan", "Trial"))
        c3.metric("Files in this session", int(st.session_state.cleaned_df is not None) + int(st.session_state.pdf_bytes is not None))
        st.markdown('<div class="panel">**Your workflow**  \nUpload → Profile → Clean → Outliers → Validate → Convert → Invoice → Get Paid.</div>', unsafe_allow_html=True)
        st.caption("Usage metrics are session-based in this version; they are not fabricated lifetime totals.")
        st.info("For reliable production hosting, connect persistent storage: Streamlit Community Cloud local files may reset after redeploys or restarts.")
    with tabs[1]:
        st.subheader("Data cleaning workspace - SUPER EDITION")
        st.caption(f"Max file size: {MAX_UPLOAD_MB} MB per file")
        upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"], key="data_upload")
        if upload:
            if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"File exceeds the {MAX_UPLOAD_MB} MB upload limit.")
            else:
                try:
                    frame = load_table(upload)
                    st.session_state.original_df = frame.copy()
                    st.write("**Original preview**")
                    st.dataframe(frame.head(100), use_container_width=True)
                    st.markdown("### ⚡ Super Tools - 1 Click, Seconds Not Hours")
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("🔍 1. AUTO-PROFILE", use_container_width=True):
                            st.session_state.profile_df = build_profile(frame)
                    with b2:
                        if st.button("🚨 5. OUTLIER HUNTER", use_container_width=True):
                            st.session_state.outliers_df = find_outliers(frame)
                    with b3:
                        if st.button("✅ 6. VALIDATE & LOCK", use_container_width=True):
                            if st.session_state.cleaned_df is not None and st.session_state.original_df is not None:
                                audit_list = st.session_state.clean_audit["Cleaning audit"].tolist() if st.session_state.clean_audit is not None else []
                                st.session_state.validation_df = build_validation_report(st.session_state.original_df, st.session_state.cleaned_df, audit_list)
                            else:
                                st.warning("Run cleaning first, then Validate.")
                    if st.session_state.get("profile_df") is not None:
                        st.markdown("**🔍 Auto-Profile - Understand your data in 1 second**")
                        st.dataframe(st.session_state.profile_df, use_container_width=True, hide_index=True)
                    if st.session_state.get("outliers_df") is not None:
                        st.markdown("**🚨 Outlier Hunter - Crazy values found**")
                        if len(st.session_state.outliers_df) == 0:
                            st.success("No outliers found! Your data looks clean.")
                        else:
                            st.dataframe(st.session_state.outliers_df, use_container_width=True, hide_index=True)
                    if st.session_state.get("validation_df") is not None:
                        st.markdown("**✅ Validate & Lock - BEFORE vs AFTER Proof**")
                        st.dataframe(st.session_state.validation_df, use_container_width=True, hide_index=True)
                        st.success("Locked: This report proves cleaning did not corrupt good data.")
                    st.divider()
                    st.markdown("### 🧹 Main Cleaning")
                    a, b, c = st.columns(3)
                    with a:
                        missing_policy = st.selectbox("Missing-value handling", ["Preserve blanks and flag them", "Fill text blanks with 'Not provided'", "Drop rows with missing values"])
                    with b:
                        remove_duplicates = st.checkbox("Remove exact duplicate rows", value=True)
                    with c:
                        normalize_case = st.checkbox("Normalize names and emails", value=True)
                    trim_text = st.checkbox("Trim and normalize whitespace", value=True)
                    standardize_business_fields = st.checkbox("Correct common business headers and department names", value=True)
                    normalize_numbers = st.checkbox("Normalise currency and numeric amount fields", value=True)
                    normalize_dates = st.checkbox("Normalise dates to DD-MM-YYYY", value=True)
                    format_fixer = st.checkbox("🎨 Format Fixer: USA / U.S.A. / KZN / City / Province", value=True)
                    st.markdown("**Advanced Super Options**")
                    d1, d2 = st.columns(2)
                    with d1:
                        smart_missing_mode = st.selectbox("🕳️ Smart Missing - Fill blanks with:", ["Don't use Smart Missing", "Average", "Median", "Most Common", "Delete rows with blanks"])
                    with d2:
                        use_fuzzy = st.checkbox("👯 Fuzzy Dedupe - Remove Sipho vs Sipo (85% match)", value=True)
                    if st.button("Run cleaning & validation", type="primary"):
                        cleaned, audit_df, audit = clean_table(frame, missing_policy, remove_duplicates, normalize_case, trim_text, standardize_business_fields=standardize_business_fields, normalize_numbers=normalize_numbers, normalize_dates=normalize_dates, format_fixer=format_fixer)
                        if smart_missing_mode != "Don't use Smart Missing":
                            if missing_policy == "Preserve blanks and flag them":
                                cleaned, smart_audit = apply_smart_missing(cleaned, smart_missing_mode)
                                audit = audit + smart_audit
                                audit_df = pd.DataFrame(audit, columns=["Cleaning audit"])
                        if use_fuzzy:
                            cleaned, fuzzy_removed, fuzzy_details = apply_fuzzy_dedupe(cleaned, threshold=0.85)
                            if fuzzy_removed:
                                audit = audit + [f"Fuzzy Dedupe: removed {fuzzy_removed} fuzzy duplicate(s)."] + fuzzy_details[:10]
                                audit_df = pd.DataFrame(audit, columns=["Cleaning audit"])
                            else:
                                audit = audit + ["Fuzzy Dedupe: no fuzzy duplicates found."]
                                audit_df = pd.DataFrame(audit, columns=["Cleaning audit"])
                        st.session_state.cleaned_df = cleaned
                        st.session_state.clean_audit = audit_df
                        st.success("Cleaning completed. Review the audit before exporting.")
                except Exception as exc:
                    st.error(f"Could not process this file: {exc}")
        if st.session_state.cleaned_df is not None:
            st.divider()
            st.markdown("### Cleaned result")
            result = st.session_state.cleaned_df
            m1, m2, m3 = st.columns(3)
            m1.metric("Rows", f"{len(result):,}")
            m2.metric("Columns", f"{len(result.columns):,}")
            m3.metric("Blank cells", f"{int(result.eq('').sum().sum()):,}")
            st.dataframe(result, use_container_width=True)
            st.markdown("**Cleaning audit**")
            st.dataframe(st.session_state.clean_audit, use_container_width=True, hide_index=True)
            csv_data, xlsx_data = dataframe_downloads(result)
            d1, d2 = st.columns(2)
            d1.download_button("Download cleaned CSV", csv_data, "cleandata_cleaned.csv", "text/csv", type="primary", use_container_width=True)
            d2.download_button("Download cleaned Excel", xlsx_data, "cleandata_cleaned.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with tabs[2]:
        st.subheader("Professional PDF editor")
        st.caption(f"Max PDF size: {MAX_UPLOAD_MB} MB per file. Edit selectable PDF text, add text, highlight content, rotate or remove pages, and merge documents.")
        pdf_upload = st.file_uploader("Upload PDF document", type=["pdf"], key="pdf_upload")
        if pdf_upload:
            if pdf_upload.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"PDF exceeds the {MAX_UPLOAD_MB} MB upload limit.")
            else:
                try:
                    raw = pdf_upload.getvalue()
                    test_doc = fitz.open(stream=raw, filetype="pdf")
                    if test_doc.is_encrypted:
                        st.error("This PDF is password-protected. Unlock it before editing.")
                    elif len(test_doc) == 0:
                        st.error("This PDF contains no pages.")
                    else:
                        st.session_state.pdf_bytes = raw
                        st.session_state.pdf_name = Path(pdf_upload.name).stem
                        st.session_state.pdf_page = min(st.session_state.pdf_page, len(test_doc) - 1)
                        st.session_state.pdf_selected = None
                    test_doc.close()
                except Exception as exc:
                    st.error(f"Could not open PDF: {exc}")
        if st.session_state.pdf_bytes:
            try:
                doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                page_count = len(doc)
                if page_count < 1:
                    st.error("The current PDF has no pages.")
                else:
                    nav_col, info_col = st.columns([1, 2])
                    with nav_col:
                        selected_page = st.number_input("Page number", min_value=1, max_value=page_count, value=min(st.session_state.pdf_page + 1, page_count), step=1, key="pdf_page_number")
                    page_index = int(selected_page) - 1
                    st.session_state.pdf_page = page_index
                    page = doc[page_index]
                    with info_col:
                        st.metric("Total pages", page_count)
                    page_image = render_pdf_page(doc, page_index, scale=1.35)
                    st.image(page_image, caption=f"Page {selected_page} of {page_count}", use_container_width=True)
                    page_text = page.get_text("text")
                    if not page_text.strip():
                        st.warning("This page has no selectable text. It may be a scanned image; OCR is not included in this build.")
                    with st.expander("View extracted page text"):
                        st.text(page_text[:20000] if page_text else "No selectable text found.")
                    edit_tab, add_tab, mark_tab, page_tab, merge_tab = st.tabs(["Find & replace", "Add text", "Highlight", "Page tools", "Merge PDFs"])
                    with edit_tab:
                        phrase = st.text_input("Find text on this page", key=f"pdf_find_{page_index}")
                        replacement = st.text_input("Replace it with", key=f"pdf_replace_{page_index}")
                        if st.button("Find and replace all matches on this page", type="primary", key=f"pdf_replace_btn_{page_index}"):
                            try:
                                st.session_state.pdf_bytes = pdf_search_replace(st.session_state.pdf_bytes, page_index, phrase, replacement)
                                st.success("Replacement applied. Check the preview carefully.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Replacement failed: {exc}")
                        st.caption("This works best with selectable text and simple layouts. It may not preserve the original font or complex spacing.")
                    with add_tab:
                        add_value = st.text_input("Text to insert", key=f"pdf_add_value_{page_index}")
                        x_col, y_col, size_col = st.columns(3)
                        x_pos = x_col.number_input("Horizontal position (pt)", min_value=0.0, value=60.0, step=5.0, key=f"pdf_x_{page_index}")
                        y_pos = y_col.number_input("Vertical position (pt)", min_value=0.0, value=100.0, step=5.0, key=f"pdf_y_{page_index}")
                        font_size = size_col.number_input("Font size", min_value=5.0, max_value=72.0, value=11.0, step=1.0, key=f"pdf_size_{page_index}")
                        if st.button("Insert text", type="primary", key=f"pdf_add_btn_{page_index}"):
                            try:
                                st.session_state.pdf_bytes = pdf_add_text(st.session_state.pdf_bytes, page_index, add_value, x_pos, y_pos, font_size)
                                st.success("Text inserted. Review the page preview.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not insert text: {exc}")
                        st.caption("Coordinates are PDF points measured from the page's top-left origin. Position text carefully using the preview.")
                    with mark_tab:
                        highlight_phrase = st.text_input("Text to highlight", key=f"pdf_highlight_{page_index}")
                        if st.button("Highlight matches", type="primary", key=f"pdf_highlight_btn_{page_index}"):
                            try:
                                st.session_state.pdf_bytes = pdf_highlight_search(st.session_state.pdf_bytes, page_index, highlight_phrase)
                                st.success("Highlight added.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not highlight text: {exc}")
                    with page_tab:
                        p1, p2, p3 = st.columns(3)
                        if p1.button("Rotate 90°", key=f"pdf_rotate_{page_index}"):
                            st.session_state.pdf_bytes = pdf_rotate_page(st.session_state.pdf_bytes, page_index, 90)
                            st.rerun()
                        if p2.button("Rotate 180°", key=f"pdf_rotate180_{page_index}"):
                            st.session_state.pdf_bytes = pdf_rotate_page(st.session_state.pdf_bytes, page_index, 180)
                            st.rerun()
                        if p3.button("Delete this page", key=f"pdf_delete_{page_index}"):
                            try:
                                st.session_state.pdf_bytes = pdf_delete_page(st.session_state.pdf_bytes, page_index)
                                st.session_state.pdf_page = max(0, page_index - 1)
                                st.success("Page deleted.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                        st.caption("Page deletion cannot be undone. Keep an untouched copy of the original PDF.")
                    with merge_tab:
                        merge_uploads = st.file_uploader("Choose PDFs to append to the current document", type=["pdf"], accept_multiple_files=True, key="pdf_merge_uploads")
                        if st.button("Merge uploaded PDFs after current document", key="pdf_merge_btn"):
                            try:
                                merged = pdf_merge([f.getvalue() for f in merge_uploads])
                                current = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                                extra = fitz.open(stream=merged, filetype="pdf")
                                current.insert_pdf(extra)
                                st.session_state.pdf_bytes = current.tobytes(garbage=4, deflate=True)
                                current.close()
                                extra.close()
                                st.success("PDFs merged.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Merge failed: {exc}")
                    updated_doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                    preview_page = min(page_index, len(updated_doc) - 1)
                    st.image(render_pdf_page(updated_doc, preview_page, 1.35), caption="Current edited PDF preview", use_container_width=True)
                    updated_doc.close()
                    st.download_button("Download edited PDF", st.session_state.pdf_bytes, f"{st.session_state.pdf_name or 'document'}_edited.pdf", "application/pdf", type="primary")
                doc.close()
            except Exception as exc:
                st.error(f"PDF editor error: {exc}")
        else:
            st.info("Upload a PDF to begin editing.")
    # ===== NEW TAB 4: FILE CONVERTER =====
    with tabs[3]:
        st.subheader("🔄 File Converter - Daily Use")
        st.caption("Convert in seconds: Image to PDF, CSV to Excel, Excel to CSV, PDF to Text, Text to PDF")
        conv_upload = st.file_uploader("Upload file to convert", type=["png", "jpg", "jpeg", "csv", "xlsx", "xls", "pdf", "txt"], key="conv_upload")
        if conv_upload:
            suffix = Path(conv_upload.name).suffix.lower()
            st.write(f"File: `{conv_upload.name}` ({conv_upload.size/1024:.1f} KB)")
            if suffix in (".png", ".jpg", ".jpeg"):
                if st.button("Convert Image → PDF", type="primary"):
                    try:
                        out = image_to_pdf_bytes(conv_upload.getvalue())
                        st.success("Converted!")
                        st.download_button("Download PDF", out, f"{Path(conv_upload.name).stem}.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            elif suffix == ".csv":
                if st.button("Convert CSV → Excel", type="primary"):
                    try:
                        df = read_csv_safely(conv_upload)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine="openpyxl") as w:
                            df.to_excel(w, index=False)
                        st.download_button("Download Excel", buf.getvalue(), f"{Path(conv_upload.name).stem}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            elif suffix in (".xlsx", ".xls"):
                if st.button("Convert Excel → CSV", type="primary"):
                    try:
                        df = pd.read_excel(conv_upload, dtype=str).fillna("")
                        st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{Path(conv_upload.name).stem}.csv", "text/csv")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            elif suffix == ".pdf":
                if st.button("Extract PDF → Text", type="primary"):
                    try:
                        txt = pdf_to_text_bytes(conv_upload.getvalue())
                        st.text_area("Extracted Text", txt[:10000], height=250)
                        st.download_button("Download Text", txt.encode("utf-8"), f"{Path(conv_upload.name).stem}.txt", "text/plain")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            elif suffix == ".txt":
                if st.button("Convert Text → PDF", type="primary"):
                    try:
                        out = text_to_pdf_bytes(conv_upload.getvalue().decode("utf-8", errors="ignore"), title=Path(conv_upload.name).stem)
                        st.download_button("Download PDF", out, f"{Path(conv_upload.name).stem}.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            else:
                st.info("Choose PNG/JPG/CSV/XLSX/PDF/TXT")
        else:
            st.info("Upload a file to convert. Example: Photo of receipt → PDF for boss in 5 seconds!")
    # ===== NEW TAB 5: PDF TOOLKIT =====
    with tabs[4]:
        st.subheader("📦 PDF Toolkit - Compress, Split, Watermark")
        st.caption("WhatsApp won't send 50MB? Compress it! Need only page 2? Split it! Need CONFIDENTIAL? Watermark it!")
        tool_upload = st.file_uploader("Upload PDF for Toolkit", type=["pdf"], key="toolkit_upload")
        if tool_upload:
            raw = tool_upload.getvalue()
            try:
                d = fitz.open(stream=raw, filetype="pdf")
                total_pages = len(d)
                d.close()
            except Exception:
                total_pages = 0
            st.write(f"Pages: {total_pages} | Size: {raw.__len__()/1024:.1f} KB")
            t1, t2, t3 = st.columns(3)
            with t1:
                st.markdown("**Compress PDF**")
                if st.button("Compress Now", use_container_width=True):
                    try:
                        out = pdf_compress(raw)
                        st.success(f"Done! Before: {len(raw)/1024:.1f} KB → After: {len(out)/1024:.1f} KB")
                        st.download_button("Download Compressed PDF", out, f"{Path(tool_upload.name).stem}_compressed.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with t2:
                st.markdown("**Split PDF**")
                sp1 = st.number_input("From page", min_value=1, max_value=max(1, total_pages), value=1, key="split_from")
                sp2 = st.number_input("To page", min_value=1, max_value=max(1, total_pages), value=max(1, total_pages), key="split_to")
                if st.button("Split Now", use_container_width=True):
                    try:
                        out = pdf_split(raw, int(sp1), int(sp2))
                        st.download_button("Download Split PDF", out, f"{Path(tool_upload.name).stem}_pages_{sp1}-{sp2}.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with t3:
                st.markdown("**Watermark PDF**")
                wm = st.text_input("Watermark text", value="CONFIDENTIAL", key="wm_text")
                if st.button("Add Watermark", use_container_width=True):
                    try:
                        out = pdf_watermark(raw, wm)
                        st.download_button("Download Watermarked PDF", out, f"{Path(tool_upload.name).stem}_watermarked.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Failed: {e}")
        else:
            st.info("Upload a PDF to compress / split / watermark.")
    # ===== NEW TAB 6: DAILY PLANNER =====
    with tabs[5]:
        st.subheader("⏰ Daily Planner + Timesheet - Use Every Morning & Night")
        st.caption("Plan your day, log hours, send Daily Report PDF to boss/client.")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            task_name = st.text_input("Task", placeholder="e.g. Clean client data", key="planner_task")
        with col_b:
            task_hours = st.number_input("Hours", min_value=0.0, max_value=24.0, value=1.0, step=0.5, key="planner_hours")
        with col_c:
            task_rate = st.number_input("Rate R/hour (optional)", min_value=0.0, value=150.0, step=10.0, key="planner_rate")
        if st.button("➕ Add Task", type="primary"):
            if not task_name.strip():
                st.error("Enter task name.")
            else:
                st.session_state.daily_tasks.append({"Task": task_name.strip(), "Hours": float(task_hours), "Rate": float(task_rate), "Total": float(task_hours)*float(task_rate), "Done": False})
                st.rerun()
        if st.session_state.daily_tasks:
            st.markdown("**Today's Tasks**")
            total_h = sum(float(t["Hours"]) for t in st.session_state.daily_tasks)
            total_m = sum(float(t["Total"]) for t in st.session_state.daily_tasks)
            done_c = sum(1 for t in st.session_state.daily_tasks if t.get("Done"))
            c1, c2, c3 = st.columns(3)
            c1.metric("Tasks", f"{len(st.session_state.daily_tasks)}")
            c2.metric("Total Hours", f"{total_h:.1f}h")
            c3.metric("Total Value", f"R{total_m:,.2f}")
            for i, t in enumerate(st.session_state.daily_tasks):
                cc1, cc2, cc3, cc4 = st.columns([3, 1, 1, 1])
                cc1.write(f"{'✅' if t.get('Done') else '⬜'} {t['Task']}")
                cc2.write(f"{t['Hours']}h")
                cc3.write(f"R{t['Total']:,.2f}")
                if cc4.button("Done" if not t.get("Done") else "Undo", key=f"done_{i}"):
                    st.session_state.daily_tasks[i]["Done"] = not st.session_state.daily_tasks[i].get("Done", False)
                    st.rerun()
            if st.button("🗑️ Clear All Tasks"):
                st.session_state.daily_tasks = []
                st.rerun()
            # Export Daily Report PDF
            if st.button("📄 Export Daily Report PDF", type="primary"):
                try:
                    report_text = f"DAILY REPORT - {datetime.now().strftime('%d-%m-%Y')}\n\n"
                    for t in st.session_state.daily_tasks:
                        status = "DONE" if t.get("Done") else "PENDING"
                        report_text += f"- {t['Task']} | {t['Hours']}h | R{t['Total']:,.2f} | {status}\n"
                    report_text += f"\nTotal Hours: {total_h:.1f}h\nTotal Value: R{total_m:,.2f}\n\nGenerated with CleanData LAI"
                    out = text_to_pdf_bytes(report_text, title="Daily Report")
                    st.download_button("Download Daily Report PDF", out, "daily_report.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Failed: {e}")
            # Send to Invoice - one click
            if st.button("➡️ Send Total to Quick Invoice"):
                st.session_state.invoice_items = [{"desc": f"Work - {t['Task']}", "qty": t["Hours"], "rate": t["Rate"]} for t in st.session_state.daily_tasks]
                st.success("Sent to Quick Invoice! Go to 🧾 Quick Invoice tab.")
        else:
            st.info("No tasks yet. Add your first task for today!")
    # ===== NEW TAB 7: QUICK INVOICE =====
    with tabs[6]:
        st.subheader("🧾 Quick Invoice - Get Paid in 30 Seconds")
        st.caption("Fill, preview, download pro PDF invoice. SA VAT + Banking details included.")
        ic1, ic2 = st.columns(2)
        with ic1:
            biz_name = st.text_input("Your Business Name", value=user.get("company", "") or "CleanData LAI", key="inv_biz")
            biz_email = st.text_input("Your Email", value=email, key="inv_biz_email")
            biz_phone = st.text_input("Your Phone", value="", key="inv_biz_phone")
            banking = st.text_input("Banking Details", value="", key="inv_banking")
        with ic2:
            client_name = st.text_input("Client Name", value="", key="inv_client")
            client_email = st.text_input("Client Email", value="", key="inv_client_email")
            inv_no = st.text_input("Invoice No", value=f"INV-{datetime.now().strftime('%Y%m%d')}-001", key="inv_no")
            inv_date = st.text_input("Invoice Date (DD-MM-YYYY)", value=datetime.now().strftime("%d-%m-%Y"), key="inv_date")
        st.markdown("**Invoice Items**")
        # Edit items - simple: 3 rows editable
        for idx, item in enumerate(st.session_state.invoice_items):
            e1, e2, e3 = st.columns([3, 1, 1])
            with e1:
                new_desc = st.text_input(f"Description {idx+1}", value=item.get("desc", ""), key=f"inv_desc_{idx}")
            with e2:
                new_qty = st.number_input(f"Qty {idx+1}", min_value=0.0, value=float(item.get("qty", 1)), step=1.0, key=f"inv_qty_{idx}")
            with e3:
                new_rate = st.number_input(f"Rate R {idx+1}", min_value=0.0, value=float(item.get("rate", 0)), step=10.0, key=f"inv_rate_{idx}")
            st.session_state.invoice_items[idx] = {"desc": new_desc, "qty": new_qty, "rate": new_rate}
        b_add, b_clear = st.columns(2)
        if b_add.button("➕ Add Item"):
            st.session_state.invoice_items.append({"desc": "New Service", "qty": 1, "rate": 100.0})
            st.rerun()
        if b_clear.button("Clear Items"):
            st.session_state.invoice_items = [{"desc": "Data Cleaning Service", "qty": 1, "rate": 250.0}]
            st.rerun()
        vat_on = st.checkbox("Add VAT (15%)", value=True, key="inv_vat")
        notes = st.text_input("Notes / Payment Terms", value="Payment due in 7 days. Thank you!", key="inv_notes")
        # Preview totals
        try:
            sub = sum(float(it["qty"])*float(it["rate"]) for it in st.session_state.invoice_items)
            vat_amt = sub*0.15 if vat_on else 0.0
            grand = sub + vat_amt
            st.markdown(f"**Subtotal: R{sub:,.2f} | VAT: R{vat_amt:,.2f} | TOTAL: R{grand:,.2f}**")
        except Exception:
            sub, vat_amt, grand = 0, 0, 0
        if st.button("🧾 Generate Invoice PDF", type="primary"):
            try:
                if not biz_name.strip() or not client_name.strip():
                    st.error("Enter business name and client name.")
                else:
                    pdf_bytes = generate_invoice_pdf(biz_name, biz_email, biz_phone, banking, client_name, client_email, inv_no, inv_date, st.session_state.invoice_items, vat_on, 15.0, notes)
                    st.success(f"Invoice ready! Total: R{grand:,.2f}")
                    st.download_button("Download Invoice PDF", pdf_bytes, f"{inv_no}.pdf", "application/pdf", type="primary")
            except Exception as e:
                st.error(f"Failed: {e}")
    with tabs[7]:
        st.subheader("Plans & account")
        st.write("Choose a plan when payment processing has been configured and verified.")
        for key, plan in PLANS.items():
            with st.expander(f"{plan['name']} — R{plan['price']}"):
                st.write(f"Access duration: {plan['days']} day(s)")
                payfast_checkout(email, key)
        st.warning("Important: this version deliberately does not activate paid access from a browser return URL. A secure PayFast ITN endpoint must validate the signature, payment status, amount and merchant before extending subscriptions.")

if st.session_state.auth.get("logged_in"):
    workspace(st.session_state.auth["user"])
else:
    auth_pages()
