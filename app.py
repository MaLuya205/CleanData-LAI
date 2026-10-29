import streamlit as st
import pandas as pd
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from datetime import datetime, timedelta
import json, os, hashlib, random

st.set_page_config(page_title="CleanData LAI - KZN", layout="wide")

# ---------- SA TIMEZONE - FIXED FOR KZN ----------
def now_sa():
    # SAST = UTC+2, naive datetime to avoid TypeError
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Africa/Johannesburg")).replace(tzinfo=None)
    except:
        try:
            import pytz
            return datetime.now(pytz.timezone("Africa/Johannesburg")).replace(tzinfo=None)
        except:
            return datetime.now() + timedelta(hours=2)

def safe_parse_date(date_str):
    # Handles old users without timezone and new users with +02:00
    if not date_str:
        return now_sa()
    try:
        dt = datetime.fromisoformat(str(date_str))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return now_sa()

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# ---------- PRICING YOU WANTED ----------
PLANS = {
    "1day": {"name": "1 Day Pass", "price": "100.00", "days": 1},
    "1week": {"name": "1 Week Pass", "price": "570.00", "days": 7},
    "1month": {"name": "1 Month Pro", "price": "2250.00", "days": 30}
}

USERS_FILE = "users_db.json"
USE_FIREBASE = False
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    if "firebase" in st.secrets:
        cred_dict = dict(st.secrets["firebase"])
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
except Exception as e:
    USE_FIREBASE = False

def load_users_local():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users_local(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def generate_code():
    return str(random.randint(100000, 999999))

# ---------- SIGNUP WITH EMAIL VERIFICATION ----------
def signup(email, password):
    email = email.lower().strip()
    pwd_hash = hash_pwd(password)
    code = generate_code()
    created = now_sa().isoformat()
    trial_until = (now_sa() + timedelta(hours=24)).isoformat()
    verify_exp = (now_sa() + timedelta(minutes=15)).isoformat()
    
    if USE_FIREBASE:
        doc_ref = db.collection("users").document(email)
        if doc_ref.get().exists:
            return False, "❌ User already exists! Please Login.", None
        doc_ref.set({
            "password": pwd_hash,
            "created_at": created,
            "paid_until": trial_until,
            "trial_expires": trial_until,
            "plan": "trial",
            "verified": False,
            "verify_code": code,
            "verify_expires": verify_exp,
            "timezone": "Africa/Johannesburg"
        })
        return True, f"✅ Account created! Code sent to {email}", code
    
    users = load_users_local()
    if email in users:
        return False, "❌ User already exists! Please Login.", None
    users[email] = {
        "password": pwd_hash,
        "created_at": created,
        "paid_until": trial_until,
        "trial_expires": trial_until,
        "plan": "trial",
        "verified": False,
        "verify_code": code,
        "verify_expires": verify_exp,
        "timezone": "Africa/Johannesburg"
    }
    save_users_local(users)
    return True, f"✅ Account created! Code sent to {email}", code

def verify_email_func(email, code):
    email = email.lower().strip()
    if USE_FIREBASE:
        doc_ref = db.collection("users").document(email)
        doc = doc_ref.get()
        if not doc.exists:
            return False, "❌ Email not found."
        data = doc.to_dict()
        if data.get("verified"):
            return True, "✅ Already verified! You can login."
        if data.get("verify_code") != code:
            return False, "❌ Wrong code."
        exp = safe_parse_date(data.get("verify_expires"))
        if now_sa() > exp:
            return False, "❌ Code expired. Sign up again."
        doc_ref.update({"verified": True})
        return True, f"✅ Email verified! SA Time: {now_sa().strftime('%Y-%m-%d %H:%M SAST')}"
    
    users = load_users_local()
    if email not in users:
        return False, "❌ Email not found."
    if users[email].get("verified"):
        return True, "✅ Already verified!"
    if users[email].get("verify_code") != code:
        return False, "❌ Wrong code."
    exp = safe_parse_date(users[email].get("verify_expires"))
    if now_sa() > exp:
        return False, "❌ Code expired. Sign up again."
    users[email]["verified"] = True
    save_users_local(users)
    return True, f"✅ Email verified! Time: {now_sa().strftime('%Y-%m-%d %H:%M SAST')}"

def login(email, password):
    email = email.lower().strip()
    pwd_hash = hash_pwd(password)
    if USE_FIREBASE:
        doc_ref = db.collection("users").document(email)
        doc = doc_ref.get()
        if not doc.exists:
            return False, "❌ Email not found. Sign up first."
        data = doc.to_dict()
        if not data.get("verified"):
            return False, "❌ Email not verified! Go to Verify Email tab."
        if data["password"] != pwd_hash:
            return False, "❌ Wrong password."
        exp = safe_parse_date(data.get("paid_until"))
        if now_sa() > exp:
            return False, f"❌ {data.get('plan')} expired {exp.strftime('%Y-%m-%d %H:%M SAST')}. Renew below!"
        return True, f"✅ Active until {exp.strftime('%Y-%m-%d %H:%M SAST')}"
    
    users = load_users_local()
    if email not in users:
        return False, "❌ Email not found."
    if not users[email].get("verified"):
        return False, "❌ Email not verified! Go to Verify Email tab."
    if users[email]["password"] != pwd_hash:
        return False, "❌ Wrong password."
    exp = safe_parse_date(users[email].get("paid_until"))
    if now_sa() > exp:
        return False, f"❌ Expired {exp.strftime('%Y-%m-%d %H:%M SAST')}. Renew!"
    return True, f"✅ Active until {exp.strftime('%Y-%m-%d %H:%M SAST')}"

def get_user_status(email):
    email = email.lower().strip()
    if USE_FIREBASE:
        doc = db.collection("users").document(email).get()
        if doc.exists:
            d = doc.to_dict()
            exp = safe_parse_date(d.get("paid_until") or d.get("trial_expires"))
            return (now_sa() < exp), exp, d.get("plan", "trial")
        return False, None, "not_found"
    users = load_users_local()
    if email in users:
        exp = safe_parse_date(users[email].get("paid_until") or users[email].get("trial_expires"))
        return (now_sa() < exp), exp, users[email].get("plan", "trial")
    return False, None, "not_found"

def extend_subscription(email, plan_key):
    email = email.lower().strip()
    days = PLANS[plan_key]["days"]
    new_until = now_sa() + timedelta(days=days)
    if USE_FIREBASE:
        db.collection("users").document(email).update({
            "paid_until": new_until.isoformat(),
            "plan": plan_key,
            "last_payment": now_sa().isoformat(),
            "amount_paid": PLANS[plan_key]["price"]
        })
    else:
        users = load_users_local()
        if email in users:
            users[email]["paid_until"] = new_until.isoformat()
            users[email]["plan"] = plan_key
            users[email]["last_payment"] = now_sa().isoformat()
            save_users_local(users)
    return new_until

# ---------- PAYFAST FULL ----------
def get_payfast_creds():
    if "payfast" in st.secrets and "payfast" in st.secrets:
        try:
            return st.secrets["payfast"]["merchant_id"], st.secrets["payfast"]["merchant_key"], "https://www.payfast.co.za/eng/process"
        except:
            pass
    return "10000100", "46f0cd694581a", "https://sandbox.payfast.co.za/eng/process"

def payfast_button(email, plan_key):
    plan = PLANS[plan_key]
    mid, mkey, url = get_payfast_creds()
    data = {
        "merchant_id": mid,
        "merchant_key": mkey,
        "return_url": f"https://cleandatalai.co.za?payment=success&plan={plan_key}&email={email}",
        "cancel_url": "https://cleandatalai.co.za?payment=cancelled",
        "notify_url": "https://cleandatalai.co.za/api/notify",
        "m_payment_id": f"{email}|{plan_key}|{now_sa().timestamp()}",
        "amount": plan["price"],
        "item_name": f"CleanData LAI {plan['name']}",
        "item_description": f"{plan['days']} days access - KZN",
        "email_address": email,
        "email_confirmation": "1",
        "confirmation_address": email
    }
    html = f'<form action="{url}" method="post" style="margin:10px 0;">'
    for k, v in data.items():
        html += f'<input type="hidden" name="{k}" value="{v}">'
    color = "#ff6600" if plan_key == "1day" else "#0066ff" if plan_key == "1week" else "#00aa44"
    html += f'<button type="submit" style="background:{color};color:white;padding:14px 20px;border:none;border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer;width:100%;">🔒 Pay R{plan["price"]} - {plan["name"]}</button></form>'
    return html

# ---------- CLEANING - R + SALES FIX ----------
def clean_data(df):
    original_count = len(df)
    df = df.dropna(how='all')
    df = df[~df.astype(str).apply(lambda x: x.str.contains('#ERROR|N/A', na=False)).any(axis=1)]
    df.columns = [str(c).strip() for c in df.columns]
    
    if len(df.columns) >= 4:
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if "name" in lc: col_map[c] = "Full Name"
            elif "phone" in lc or "cell" in lc or "tel" in lc: col_map[c] = "Phone Number"
            elif "email" in lc or "mail" in lc: col_map[c] = "Email"
            elif "amount" in lc or "rand" in lc or "price" in lc or "owes" in lc: col_map[c] = "Amount (R)"
            elif "sale" in lc: col_map[c] = "Sales"
            elif "location" in lc or "address" in lc: col_map[c] = "Location"
            elif "date" in lc: col_map[c] = "Date"
        df = df.rename(columns=col_map)

    if "Full Name" in df.columns:
        df["Full Name"] = df["Full Name"].astype(str).str.strip().str.title()
        df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)

    if "Phone Number" in df.columns:
        df["Phone Number"] = df["Phone Number"].astype(str).str.replace(r'\D', '', regex=True)
        df["Phone Number"] = df["Phone Number"].apply(lambda x: x[-10:] if len(x) >= 10 else x)

    if "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.strip().str.lower().str.replace(' ', '').str.replace(',', '.')

    if "Amount (R)" in df.columns:
        df["Amount (R)"] = df["Amount (R)"].astype(str).str.replace(',', '', regex=False)
        df["Amount (R)"] = df["Amount (R)"].str.extract(r'(\d+\.?\d*)')[0]
        def format_r(x):
            if pd.isna(x) or str(x).strip() == "" or str(x).lower() == 'nan':
                return ""
            try:
                return f"R {float(x):.2f}"
            except:
                return ""
        df["Amount (R)"] = df["Amount (R)"].apply(format_r)

    # SALES FIX - ALL CATEGORY COLUMNS TITLE CASE
    for col in df.columns:
        if col not in ["Full Name", "Phone Number", "Email", "Amount (R)"]:
            df[col] = df[col].astype(str).str.strip().str.lower().str.title()
            df[col] = df[col].str.replace(r'\s+', ' ', regex=True)

    if "Full Name" in df.columns:
        df = df[df["Full Name"].astype(str).str.len() > 2]
        if "Phone Number" in df.columns:
            df = df.drop_duplicates(subset=["Full Name", "Phone Number"], keep='first')
    if "Email" in df.columns:
        df = df.drop_duplicates(subset=["Email"], keep='first')

    cleaned_count = len(df)
    removed = original_count - cleaned_count
    return df, original_count, cleaned_count, removed

# ---------- UI ----------
st.title("🧹 CleanData LAI - KZN Stock Cleaner")
st.caption(f"SA Time: {now_sa().strftime('%Y-%m-%d %H:%M SAST')} | Africa/Johannesburg | Plans: R100 / R570 / R2250")

# PAYFAST RETURN HANDLING
qp = st.query_params
if qp.get("payment") == "success":
    p = qp.get("plan", "1day")
    em = qp.get("email", "")
    if em and p in PLANS:
        try:
            new_until = extend_subscription(em, p)
            st.success(f"🎉 Payment Success! {PLANS[p]['name']} active until {new_until.strftime('%Y-%m-%d %H:%M SAST')}")
            st.balloons()
        except Exception as e:
            st.warning(f"Payment received! Contact support: {e}")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if not USE_FIREBASE:
    st.warning("⚠️ LOCAL mode - add Firebase in Secrets for real website.")

if not st.session_state.logged_in:
    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Verify Email"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            ok, msg = login(email, pwd)
            if ok:
                st.session_state.logged_in = True
                st.session_state.user_email = email.lower()
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    with tab2:
        email2 = st.text_input("Email", key="signup_email")
        pwd2 = st.text_input("Password", type="password", key="signup_pwd")
        if st.button("Create Account - Send Verification Code"):
            ok, msg, code = signup(email2, pwd2)
            if ok:
                st.success(msg)
                st.info(f"🔐 TEST MODE CODE: **{code}** (Copy and go to Verify Email tab)")
                st.warning("In live site, code goes to email via SendGrid")
            else:
                st.error(msg)
    with tab3:
        st.markdown("### 📧 Verify Your Email")
        ev = st.text_input("Email to verify", key="ve")
        cv = st.text_input("6-digit code", key="vc")
        if st.button("Verify Email Now"):
            ok, msg = verify_email_func(ev, cv)
            if ok:
                st.success(msg)
                st.info("Now go to Login tab!")
            else:
                st.error(msg)
    st.stop()

# LOGGED IN
st.sidebar.write(f"✅ Logged: {st.session_state.user_email}")
is_active, expires, current_plan = get_user_status(st.session_state.user_email)

if not is_active:
    st.sidebar.error(f"❌ Expired: {current_plan} on {expires.strftime('%Y-%m-%d %H:%M SAST') if expires else ''}")
    st.error(f"⏰ Your {current_plan} expired! Please renew.")
    st.markdown("### 💰 Choose Your Plan - CleanData LAI KZN")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 📅 1 Day Pass\n### R100\n- 1 Day\n- 500 rows")
        st.markdown(payfast_button(st.session_state.user_email, "1day"), unsafe_allow_html=True)
    with col2:
        st.markdown("#### 🔥 1 Week\n### R570\n**MOST POPULAR**\n- 7 Days\n- 5000 rows")
        st.markdown(payfast_button(st.session_state.user_email, "1week"), unsafe_allow_html=True)
    with col3:
        st.markdown("#### 🚀 1 Month\n### R2250\n**COMPANIES**\n- 30 Days\n- Unlimited")
        st.markdown(payfast_button(st.session_state.user_email, "1month"), unsafe_allow_html=True)
    st.info("💳 Card / Instant EFT / Capitec Pay - Secured by PayFast")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.rerun()
    st.stop()
else:
    st.sidebar.success(f"✅ Active: {current_plan} until {expires.strftime('%Y-%m-%d %H:%M SAST')}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.rerun()

uploaded = st.file_uploader("Upload messy CSV, Excel or Image (JPG/PNG/PDF)", type=["csv","xlsx","xls","jpg","jpeg","png","pdf"])

if uploaded:
    try:
        df = pd.DataFrame()
        if uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded, dtype=str)
        elif uploaded.name.lower().endswith((".xlsx","xls")):
            df = pd.read_excel(uploaded, dtype=str)
        elif uploaded.name.lower().endswith(".pdf"):
            pdf_bytes = uploaded.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            lines = [l for l in text.split('\n') if l.strip()]
            if len(lines) < 3:
                pix = doc[0].get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img)
                lines = [l for l in text.split('\n') if l.strip()]
            data = [l.split(',') for l in lines]
            df = pd.DataFrame(data[1:], columns=data[0] if data else None)
        else:
            image = Image.open(uploaded)
            text = pytesseract.image_to_string(image)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if lines:
                header = [h.strip() for h in re.split(r'\s{2,}|\t|,|\|', lines[0]) if h.strip()]
                rows = []
                for line in lines[1:]:
                    parts = [p.strip() for p in re.split(r'\s{2,}|\t|,|\|', line) if p.strip()]
                    if len(parts) >= 3:
                        rows.append(parts)
                if rows:
                    df = pd.DataFrame(rows, columns=header[:len(rows[0])] if len(header)>=len(rows[0]) else None)
        
        if df.empty:
            st.error("Could not read file. Try CSV/Excel for 100% result.")
        else:
            st.write("Original Preview:")
            st.dataframe(df.head(20))
            if st.button("Clean Data Now - Excel Formulas", type="primary"):
                cleaned_df, orig, cleaned, removed = clean_data(df)
                st.success(f"Cleaned! Original: {orig} → Cleaned: {cleaned} | Removed: {removed}")
                st.write("Cleaned Data - FIXED Rands & Sales")
                st.dataframe(cleaned_df)
                csv = cleaned_df.to_csv(index=False).encode('utf-8')
                st.download_button("⬇️ Download Clean CSV", csv, "cleaned_with_rands_sales.csv", "text/csv")
    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)
