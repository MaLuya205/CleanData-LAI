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

# ===== NEW FIX: SMART EMAIL REPAIR =====
def _score_email(email: str, full_name: str) -> int:
    """Score which email is most likely CORRECT for this person.
    thandinene@gmail.com beats thandi@nene.com because:
    - contains full name thandinene (not just thandi)
    - real domain gmail.com beats nene.com / nene
    """
    e = email.strip().lower()
    if not valid_email(e):
        return -100  # invalid like thandi@nene
    local, domain = e.split("@", 1)
    score = 0
    # Full name in email = very strong signal
    name_nospace = re.sub(r"[^a-z]", "", full_name.lower())  # thandinene
    first_name = full_name.lower().split()[0] if full_name.strip() else ""
    if local == name_nospace:
        score += 50  # thandinene == thandinene
    elif name_nospace in local:
        score += 30
    elif first_name and first_name in local:
        score += 10
    # Trusted domains
    if domain in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com"):
        score += 20
    elif "." in domain and len(domain.split(".")[-1]) >= 2:
        score += 5
    # Longer local = more complete (thandinene > thandi)
    score += len(local)
    return score

def _repair_emails(df: pd.DataFrame, audit: list[str]) -> pd.DataFrame:
    """Fix broken emails using the BEST email from same person (same Name + Phone)."""
    # Find columns
    email_col = next((c for c in df.columns if "email" in c.lower()), None)
    name_col = next((c for c in df.columns if c.lower() in ("customer name", "name", "customer", "client name")), None)
    phone_col = next((c for c in df.columns if "phone" in c.lower() or "cell" in c.lower() or "mobile" in c.lower()), None)
    if not email_col or not name_col or not phone_col:
        return df
    df = df.copy()
    fixed = 0
    # Group by Name + Phone = same person
    for (name, phone), group in df.groupby([name_col, phone_col], dropna=False):
        if len(group) < 2:
            # Single row: if invalid, we can't know correct - leave it flagged
            continue
        emails = [str(x).strip().lower() for x in group[email_col].tolist() if str(x).strip()]
        if not emails:
            continue
        # Find best valid email in group
        valid = [e for e in emails if valid_email(e)]
        if not valid:
            continue
        # Score all valid emails, pick winner
        best = max(valid, key=lambda e: _score_email(e, str(name)))
        # Fix every row in group that is NOT best
        for idx in group.index:
            cur = str(df.at[idx, email_col]).strip().lower()
            if cur != best:
                # Only fix if current is invalid OR is a "short" version of best
                # e.g. thandi@nene (invalid) -> thandinene@gmail.com
                # thandi@nene.com (valid but wrong) -> thandinene@gmail.com IF best scores much higher
                cur_score = _score_email(cur, str(name))
                best_score = _score_email(best, str(name))
                # Fix if current is invalid, OR best is clearly better (+20 points)
                if not valid_email(cur) or (best_score - cur_score >= 20):
                    df.at[idx, email_col] = best
                    fixed += 1
    if fixed:
        audit.append(f"Email: repaired {fixed} email(s) using the correct email from the same person (same Name + Phone). Example: thandi@nene / thandi@nene.com -> thandinene@gmail.com")
    return df

def clean_table(source: pd.DataFrame, missing_policy: str, remove_duplicates: bool, normalize_case: bool, trim_text: bool, standardize_business_fields: bool = True, normalize_numbers: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
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
        if col_lower == "department" and standardize_business_fields:
            new = new.map(_normalise_department)
        if is_phone_col:
            new = new.map(_clean_phone)
        elif is_email_col:
            new = new.str.lower().str.strip()
            # Don't flag yet - we will repair first, then flag what is left
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
        elif normalize_numbers and not is_phone_col:
            mask = new.str.fullmatch(r"(?i)R\s*[+-]?[\d\s,\.]+", na=False)
            if mask.any():
                new.loc[mask] = new.loc[mask].map(lambda x: _clean_currency(x, force_r=False))
        changed = int((old != new).sum())
        if changed:
            audit.append(f"{col}: standardised {changed} cell(s).")
        df[col] = new

    # ===== NEW: REPAIR EMAILS BEFORE DUPLICATE CHECK =====
    df = _repair_emails(df, audit)

    # After repair, flag any STILL-invalid emails
    email_col = next((c for c in df.columns if "email" in c.lower()), None)
    if email_col:
        invalid = df[email_col].astype(str).ne("") & ~df[email_col].astype(str).str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if invalid.any():
            audit.append(f"{email_col}: flagged {int(invalid.sum())} invalid email value(s) that could not be repaired from same person; preserved for review.")

    missing_count = int(df.eq("").sum().sum())
    if missing_policy == "Drop rows with missing values":
        before = len(df)
        df = df.replace(r"^\s*$", pd.NA, regex=True).dropna().copy()
        audit.append(f"Removed {before-len(df)} row(s) containing one or more missing values.")
    elif missing_policy == "Fill text blanks with 'Not provided'":
        for col in df.columns:
            df[col] = df[col].replace("", "Not provided")
        audit.append("Filled blank cells with 'Not provided' at the user's request.")
    else:
        audit.append(f"Preserved {missing_count} blank cell(s); no missing values were guessed.")

    # ===== NEW: SMART DUPLICATES - Email differences don't hide duplicates =====
    if remove_duplicates:
        # 1) Exact duplicates after cleaning + email repair
        before_dedup = len(df)
        df = df.drop_duplicates().copy()
        exact_removed = before_dedup - len(df)
        # 2) Smart duplicates: Same Person (Name+Phone) + Same Amount + Same Department = duplicate
        # Even if something else slightly differs, it's same transaction
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
            # Keep first occurrence - it now has repaired email
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
def find_text_span(page: fitz.Page, x: float, y: float, radius: float = 22):
    best = None
    best_distance = float("inf")
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                bbox = fitz.Rect(span.get("bbox", (0, 0, 0, 0)))
                if not text or bbox.is_empty:
                    continue
                if bbox.x0 <= x <= bbox.x1 and bbox.y0 <= y <= bbox.y1:
                    return span
                cx = (bbox.x0 + bbox.x1) / 2
                cy = (bbox.y0 + bbox.y1) / 2
                distance = ((cx-x)**2 + (cy-y)**2)**0.5
                if distance < best_distance:
                    best = span
                    best_distance = distance
    return best if best_distance <= radius else None
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
    defaults = {"auth": {"logged_in": False, "page": "signin"}, "pending_signup": None, "cleaned_df": None, "clean_audit": None, "pdf_bytes": None, "pdf_name": None, "pdf_selected": None, "pdf_page": 0}
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
        default_mode = 1 if st.session_state.pending_signup else (0 if st.session_state.auth["page"] == "signin" else 1)
        mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True, index=default_mode)
        if mode == "Create account":
            with st.form("signup_form"):
                name = st.text_input("Full name")
                company = st.text_input("Business / team")
                email = st.text_input("Email address")
                password = st.text_input("Password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                submit = st.form_submit_button("Create account & send OTP", type="primary", use_container_width=True)
            if submit:
                email = email.strip().lower()
                if not name.strip() or not company.strip() or not valid_email(email):
                    st.error("Enter your name, business and a valid email address.")
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
                        st.session_state.pending_signup = {"name": name.strip(), "company": company.strip(), "email": email, "password_hash": password_hash(password), "otp_hash": hashlib.sha256(code.encode()).hexdigest(), "created_at": time.time(), "attempts": 0}
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
                        users[pending["email"]] = {"name": pending["name"], "company": pending["company"], "password": pending["password_hash"], "verified": True, "created_at": now_utc().isoformat(), "paid_until": (now_utc() + timedelta(days=1)).isoformat(), "plan": "trial"}
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
    with st.sidebar:
        st.markdown("## 🧹 CleanData LAI")
        st.caption("Professional workspace")
        st.write(f"**{user.get('name', 'User')}**")
        st.caption(user.get("company", ""))
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
            st.rerun()
    hero()
    tabs = st.tabs(["Overview", "Data cleaning", "PDF editor", "Plans & account"])
    with tabs[0]:
        st.subheader("Workspace overview")
        c1, c2, c3 = st.columns(3)
        c1.metric("Account status", "Verified" if user.get("verified") else "Unverified")
        c2.metric("Plan", user.get("plan", "Trial"))
        c3.metric("Files in this session", int(st.session_state.cleaned_df is not None) + int(st.session_state.pdf_bytes is not None))
        st.markdown('<div class="panel">**Your workflow**  \nUpload a file → inspect the original → clean or edit → review the result → export.</div>', unsafe_allow_html=True)
        st.caption("Usage metrics are session-based in this version; they are not fabricated lifetime totals.")
        st.info("For reliable production hosting, connect persistent storage: Streamlit Community Cloud local files may reset after redeploys or restarts.")
    with tabs[1]:
        st.subheader("Data cleaning workspace")
        st.caption(f"Max file size: {MAX_UPLOAD_MB} MB per file")
        upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"], key="data_upload")
        if upload:
            if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"File exceeds the {MAX_UPLOAD_MB} MB upload limit.")
            else:
                try:
                    frame = load_table(upload)
                    st.write("**Original preview**")
                    st.dataframe(frame.head(100), use_container_width=True)
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
                    if st.button("Run cleaning & validation", type="primary"):
                        cleaned, audit_df, audit = clean_table(frame, missing_policy, remove_duplicates, normalize_case, trim_text, standardize_business_fields=standardize_business_fields, normalize_numbers=normalize_numbers)
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
    with tabs[3]:
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
