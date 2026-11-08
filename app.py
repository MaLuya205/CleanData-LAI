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

import pandas as pd
import streamlit as st
import fitz
from PIL import Image

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    HAS_IMAGE_COORDINATES = True
except Exception:
    HAS_IMAGE_COORDINATES = False

st.set_page_config(
    page_title="CleanData LAI | Workspace",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "CleanData LAI"
DATA_DIR = Path(os.getenv("CLEANDATA_DATA_DIR", ".cleandata_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
OTP_MINUTES = 10

PLANS = {
    "1day": {"name": "1 Day Pass", "price": "49.00", "days": 1},
    "1week": {"name": "1 Week Pass", "price": "149.00", "days": 7},
    "1month": {"name": "1 Month Pro", "price": "399.00", "days": 30},
}

# ---------------------------- VISUAL DESIGN ----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#eaf0ff; --muted:#9aa8c4; --panel:#111b31; --line:#263653; --accent:#70e1b2; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:radial-gradient(ellipse at 12% 0%, #192b4b 0%, #0b1222 48%, #080e1a 100%); color:var(--ink); }
h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.035em; }
[data-testid="stSidebar"] { background:#0b1426; border-right:1px solid #263653; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#172641,#101a2e); border:1px solid #2a3c5b; padding:16px; border-radius:16px; }
[data-testid="stMetricLabel"] { color:#aebbd2; }
[data-testid="stMetricValue"] { color:#f5f8ff; }
.stButton>button, .stDownloadButton>button { border-radius:11px; font-weight:700; min-height:2.7rem; }
.stButton>button[kind="primary"] { background:linear-gradient(90deg,#35bd91,#70e1b2); color:#071b18; border:0; }
div[data-testid="stForm"] { background:#111b31; padding:22px; border:1px solid #263653; border-radius:18px; }
div[data-testid="stFileUploader"] { background:#111b31; border:1px dashed #3b5278; border-radius:14px; padding:12px; }
.block-container { padding-top:2rem; padding-bottom:3rem; max-width:1500px; }
small,.muted { color:#9aa8c4; }
.hero { padding:28px; border-radius:22px; border:1px solid #2b4164; background:linear-gradient(115deg, rgba(31,60,94,.95), rgba(15,28,49,.96)); margin-bottom:20px; }
.hero-kicker { color:#70e1b2; font-size:.78rem; text-transform:uppercase; letter-spacing:.16em; font-weight:800; }
.hero h1 { font-size:2.3rem; margin:.35rem 0; color:#f7f9ff; }
.hero p { color:#bdc9dc; max-width:780px; }
.panel { background:#111b31; border:1px solid #263653; border-radius:16px; padding:18px; }
div[data-testid="stTabs"] button { font-weight:700; }
hr { border-color:#263653; }
</style>
""", unsafe_allow_html=True)

# ---------------------------- ACCOUNT SECURITY ----------------------------
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
    return (len(pwd) >= 10 and any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd) and any(not c.isalnum() for c in pwd))

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
    if len(frame) > 500_000 or len(frame.columns) > 300:
        raise ValueError("This file is larger than the current workspace limit.")
    return frame.fillna("")

def clean_table(source: pd.DataFrame, missing_policy: str, remove_duplicates: bool, normalize_case: bool, trim_text: bool) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Conservative cleaning: do not invent business values."""
    df = normalize_columns(source.copy())
    audit = []
    before = len(df)
    empty_rows = (df.replace(r"^\s*$", pd.NA, regex=True).isna().all(axis=1))
    count_empty = int(empty_rows.sum())
    if count_empty:
        df = df.loc[~empty_rows].copy()
        audit.append(f"Removed {count_empty} completely empty row(s).")
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            old = df[col].astype(str)
            if trim_text:
                new = (old.str.replace(r"[\u00a0\t\r]", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip())
                changed = int((old != new).sum())
                if changed:
                    audit.append(f"{col}: trimmed whitespace in {changed} cell(s).")
                df[col] = new
            null_mask = (df[col].str.strip().str.lower().isin(["nan", "none", "null", "n/a", "na"]))
            if null_mask.any():
                df.loc[null_mask, col] = ""
    if normalize_case:
        for col in df.columns:
            low = col.lower()
            if "email" in low:
                df[col] = (df[col].astype(str).str.strip().str.lower())
                bad = (df[col].ne("") & ~df[col].str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"))
                if bad.any():
                    audit.append(f"{col}: flagged {int(bad.sum())} invalid email value(s); values were not deleted.")
            elif any(token in low for token in ("name", "customer", "client")):
                df[col] = (df[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip().str.title())
    missing_before = int(df.eq("").sum().sum())
    if missing_policy == "Drop rows with missing values":
        old_len = len(df)
        df = (df.replace(r"^\s*$", pd.NA, regex=True).dropna().copy())
        audit.append(f"Removed {old_len-len(df)} row(s) containing one or more missing values.")
    elif missing_policy == "Fill text blanks with 'Not provided'":
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].replace("", "Not provided")
        audit.append("Filled blank text cells with 'Not provided' at the user's request.")
    else:
        audit.append(f"Preserved {missing_before} blank cell(s); no values were guessed.")
    if remove_duplicates:
        duplicates = int(df.duplicated().sum())
        if duplicates:
            df = df.drop_duplicates().copy()
        audit.append(f"Removed {duplicates} exact duplicate row(s).")
    audit.insert(0, f"Input rows: {before}; output rows: {len(df)}.")
    audit.append(f"Output columns: {len(df.columns)}.")
    return (df, pd.DataFrame(audit, columns=["Cleaning audit"]), audit)

def dataframe_downloads(df: pd.DataFrame) -> tuple[bytes, bytes]:
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned data")
    return csv_bytes, xbuf.getvalue()

# ---------------------------- PDF EDITOR ENGINE ----------------------------
def render_pdf_page(doc: fitz.Document, page_number: int, scale: float = 1.5) -> Image.Image:
    page = doc[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

def find_text_span(page: fitz.Page, x: float, y: float, radius: float = 22):
    """Find the closest selectable text span to the clicked coordinate."""
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
                if (bbox.x0 <= x <= bbox.x1 and bbox.y0 <= y <= bbox.y1):
                    return span
                cx = (bbox.x0 + bbox.x1) / 2
                cy = (bbox.y0 + bbox.y1) / 2
                distance = ((cx-x)**2 + (cy-y)**2)**0.5
                if distance < best_distance:
                    best = span
                    best_distance = distance
    return best if best_distance <= radius else None

def replace_pdf_span(pdf_bytes: bytes, page_number: int, bbox_tuple, replacement: str) -> bytes:
    """Replace selected text on the original PDF page."""
    if not replacement.strip():
        raise ValueError("Replacement text cannot be empty.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number]
        rect = fitz.Rect(bbox_tuple)
        rect.x0 -= 0.8
        rect.y0 -= 0.4
        rect.x1 += 0.8
        rect.y1 += 0.8
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=0)
        font_size = max(5, min(18, float(rect.height) * 0.78))
        result = page.insert_textbox(rect, replacement, fontname="helv", fontsize=font_size, color=(0, 0, 0), align=fitz.TEXT_ALIGN_LEFT, overlay=True)
        if result < 0:
            raise ValueError("Replacement text is too long for the selected area. Use shorter text.")
        out = doc.tobytes(garbage=4, deflate=True)
        return out
    finally:
        doc.close()

# ---------------------------- PAYFAST CONFIGURATION ----------------------------
def get_payfast_config():
    try:
        cfg = st.secrets["payfast"]
        return (str(cfg["merchant_id"]), str(cfg["merchant_key"]), str(cfg.get("process_url", "https://www.payfast.co.za/eng/process")))
    except Exception:
        return "", "", "https://sandbox.payfast.co.za/eng/process"

def payfast_checkout(email: str, plan_key: str):
    """Do not activate subscriptions from a browser return URL."""
    mid, mkey, endpoint = get_payfast_config()
    if not mid or not mkey:
        st.info("Payments are not configured yet. Add verified PayFast credentials and a server-side ITN endpoint.")
        return
    plan = PLANS[plan_key]
    st.warning("Payment activation must be confirmed by a server-side PayFast ITN validation before access is extended.")
    st.code(f"Merchant: {mid}\nPlan: {plan['name']}\nAmount: R{plan['price']}\nEndpoint: {endpoint}")

# ---------------------------- SESSION MANAGEMENT ----------------------------
def init_state():
    defaults = {
        "auth": {"logged_in": False, "page": "signin"},
        "pending_signup": None,
        "cleaned_df": None,
        "clean_audit": None,
        "pdf_bytes": None,
        "pdf_name": None,
        "pdf_selected": None,
        "pdf_page": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()
users = read_users()

# ---------------------------- MAIN DESIGN ----------------------------
def hero():
    st.markdown("""
    <div class="hero">
      <div class="hero-kicker">Clean workspace · Better decisions</div>
      <h1>Make messy data make sense.</h1>
      <p>Clean, validate, review and export business data. Edit existing PDF text directly on the page, with a preview before you download.</p>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------- LOGIN AND REGISTRATION ----------------------------
def auth_pages():
    hero()
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown("### Your business data workspace")
        st.markdown("""
        - **Data cleaning:** whitespace, blank values, duplicates and validation flags.
        - **PDF workspace:** render the original page, click text and replace it.
        - **Exports:** download cleaned CSV and Excel files.
        - **Safer accounts:** salted password hashing and email OTP verification.
        """)
        st.info("For production, configure persistent database storage and email secrets before inviting customers.")
    with right:
        default_mode = (1 if st.session_state.pending_signup else (0 if st.session_state.auth["page"] == "signin" else 1))
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
                if (not name.strip() or not company.strip() or not valid_email(email)):
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
                        st.session_state.pending_signup = {
                            "name": name.strip(),
                            "company": company.strip(),
                            "email": email,
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
                    if (time.time() - pending["created_at"] > OTP_MINUTES * 60):
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
                if (not record or not verify_password(password, record.get("password", ""))):
                    st.error("Email or password is incorrect.")
                elif not record.get("verified"):
                    st.error("This account has not completed email verification.")
                else:
                    if not record.get("password", "").startswith("pbkdf2_sha256$"):
                        record["password"] = password_hash(password)
                        write_users(users)
                    st.session_state.auth = {"logged_in": True, "user": email, "page": "signin"}
                    st.rerun()

# ---------------------------- LOGGED-IN WORKSPACE ----------------------------
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
    with tabs[1]:
        st.subheader("Data cleaning workspace")
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
                    if st.button("Run cleaning & validation", type="primary"):
                        cleaned, audit_df, audit = clean_table(frame, missing_policy, remove_duplicates, normalize_case, trim_text)
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
        st.subheader("Edit an existing PDF")
        st.caption("The original PDF page is rendered below. Click a text span to select it, enter replacement text, preview and export.")
        pdf_upload = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_upload")
        if pdf_upload:
            if pdf_upload.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"PDF exceeds the {MAX_UPLOAD_MB} MB upload limit.")
            else:
                try:
                    raw = pdf_upload.getvalue()
                    test_doc = fitz.open(stream=raw, filetype="pdf")
                    if test_doc.is_encrypted:
                        st.error("This PDF is password-protected. Unlock it before editing.")
                    else:
                        st.session_state.pdf_bytes = raw
                        st.session_state.pdf_name = Path(pdf_upload.name).stem
                        st.session_state.pdf_page = min(st.session_state.pdf_page, len(test_doc) - 1)
                    test_doc.close()
                except Exception as exc:
                    st.error(f"Could not open PDF: {exc}")
        if st.session_state.pdf_bytes:
            try:
                doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                page_count = len(doc)
                selected_page = st.number_input("Page number", min_value=1, max_value=page_count, value=min(st.session_state.pdf_page + 1, page_count), step=1)
                page_index = int(selected_page) - 1
                st.session_state.pdf_page = page_index
                page = doc[page_index]
                page_image = render_pdf_page(doc, page_index, scale=1.5)
                st.image(page_image, caption=f"Original page {selected_page} of {page_count}", use_container_width=True)
                st.caption("Click-to-select requires streamlit-image-coordinates. If unavailable, install the package listed in requirements.txt and redeploy.")
                if HAS_IMAGE_COORDINATES:
                    clicked = streamlit_image_coordinates(page_image, key=f"pdf_click_{page_index}")
                    if (clicked and clicked.get("x") is not None):
                        x = float(clicked["x"]) / 1.5
                        y = float(clicked["y"]) / 1.5
                        span = find_text_span(page, x, y)
                        if span:
                            st.session_state.pdf_selected = {"page": page_index, "bbox": span["bbox"], "text": span["text"]}
                        else:
                            st.info("No selectable text was found close to that click. Scanned/image-only text needs OCR first.")
                else:
                    st.warning("Click selection is not active because the optional click-coordinate package is missing.")
                selection = st.session_state.pdf_selected
                if (selection and selection["page"] == page_index):
                    st.markdown("**Selected text**")
                    st.code(selection["text"])
                    replacement = st.text_input("Replace selected text with", key=f"replacement_{page_index}")
                    if st.button("Apply replacement to PDF", type="primary", key=f"apply_pdf_{page_index}"):
                        try:
                            st.session_state.pdf_bytes = replace_pdf_span(st.session_state.pdf_bytes, page_index, selection["bbox"], replacement)
                            st.session_state.pdf_selected = None
                            st.success("Replacement applied to the PDF page. Review the updated page below.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not apply replacement: {exc}")
                elif not HAS_IMAGE_COORDINATES:
                    st.info("Install streamlit-image-coordinates to enable clicking directly on the page.")
                updated_doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                st.image(render_pdf_page(updated_doc, page_index, 1.5), caption="Current edited page preview", use_container_width=True)
                updated_doc.close()
                st.download_button("Download edited original PDF", st.session_state.pdf_bytes, f"{st.session_state.pdf_name or 'document'}_edited.pdf", "application/pdf", type="primary")
                doc.close()
            except Exception as exc:
                st.error(f"PDF editor error: {exc}")
        else:
            st.info("Upload a PDF to start editing.")
    with tabs[3]:
        st.subheader("Plans & account")
        st.write("Choose a plan when payment processing has been configured and verified.")
        for key, plan in PLANS.items():
            with st.expander(f"{plan['name']} — R{plan['price']}"):
                st.write(f"Access duration: {plan['days']} day(s)")
                payfast_checkout(email, key)
        st.warning("Important: this version deliberately does not activate paid access from a browser return URL. A secure PayFast ITN endpoint must validate the signature, payment status, amount and merchant before extending subscriptions.")

# ---------------------------- APPLICATION ENTRY POINT ----------------------------
if st.session_state.auth.get("logged_in"):
    workspace(st.session_state.auth["user"])
else:
    auth_pages()
