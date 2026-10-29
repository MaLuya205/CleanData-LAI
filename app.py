import streamlit as st
import pandas as pd
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from datetime import datetime, timedelta
import json, os
import hashlib

# ---------- CONFIG ----------
st.set_page_config(page_title="CleanData LAI - KZN", layout="wide")

USERS_FILE = "users_db.json"

# ---------- TRY FIREBASE - PERSISTENT, IF NOT, USE JSON ----------
USE_FIREBASE = False
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    # Check if secrets have firebase
    if "firebase" in st.secrets:
        cred_dict = dict(st.secrets["firebase"])
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
except Exception as e:
    USE_FIREBASE = False

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# ---------- PERSISTENT USER FUNCTIONS ----------
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

def signup(email, password):
    email = email.lower().strip()
    pwd_hash = hash_pwd(password)
    
    # FIREBASE MODE - PERSISTS FOREVER
    if USE_FIREBASE:
        doc_ref = db.collection("users").document(email)
        if doc_ref.get().exists:
            return False, "❌ User already exists! This email already has an account. Please Login."
        doc_ref.set({
            "password": pwd_hash,
            "created_at": datetime.now().isoformat(),
            "trial_expires": (datetime.now() + timedelta(hours=24)).isoformat(),
            "verified": True
        })
        return True, "✅ Account created! 24hr free trial started! Now Login."
    
    # LOCAL JSON MODE (will reset on Streamlit reboot - that's your bug!)
    users = load_users_local()
    if email in users:
        return False, "❌ User already exists! This email already has an account. Please Login."
    users[email] = {
        "password": pwd_hash,
        "created_at": datetime.now().isoformat(),
        "trial_expires": (datetime.now() + timedelta(hours=24)).isoformat(),
        "verified": True
    }
    save_users_local(users)
    return True, "✅ Account created! 24hr free trial started!"

def login(email, password):
    email = email.lower().strip()
    pwd_hash = hash_pwd(password)
    
    if USE_FIREBASE:
        doc_ref = db.collection("users").document(email)
        doc = doc_ref.get()
        if not doc.exists:
            return False, "❌ Email not found. Please sign up first."
        data = doc.to_dict()
        if data["password"] != pwd_hash:
            return False, "❌ Wrong password. Try again."
        expires = datetime.fromisoformat(data["trial_expires"])
        if datetime.now() > expires:
            return False, "❌ Your 24hr trial expired. Please pay R1500 to continue. Contact: 078 123 4567"
        return True, "✅ Login successful! Verified!"
    
    users = load_users_local()
    if email not in users:
        return False, "❌ Email not found. Please sign up first."
    if users[email]["password"] != pwd_hash:
        return False, "❌ Wrong password. Try again."
    expires = datetime.fromisoformat(users[email]["trial_expires"])
    if datetime.now() > expires:
        return False, "❌ Your 24hr trial expired. Please pay R1500 to continue."
    return True, "✅ Login successful!"

# ---------- CLEANING LOGIC - FIXED R ----------
def clean_data(df):
    original_count = len(df)
    df = df.dropna(how='all')
    df = df[~df.astype(str).apply(lambda x: x.str.contains('#ERROR|N/A', na=False)).any(axis=1)]
    
    df.columns = [str(c).strip() for c in df.columns]
    if len(df.columns) >= 4:
        # Map to standard names
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if "name" in lc: col_map[c] = "Full Name"
            elif "phone" in lc or "cell" in lc or "tel" in lc: col_map[c] = "Phone Number"
            elif "email" in lc or "mail" in lc: col_map[c] = "Email"
            elif "amount" in lc or "rand" in lc or "r " in lc or "price" in lc or "owes" in lc: col_map[c] = "Amount (R)"
            elif "location" in lc or "address" in lc or "kzn" in lc: col_map[c] = "Location"
            elif "date" in lc: col_map[c] = "Date"
        df = df.rename(columns=col_map)
        # Ensure order if we have at least 4 cols
        expected = ["Full Name", "Phone Number", "Email", "Amount (R)", "Location", "Date"]
        # Keep only mapped + keep original order for rest
        if "Full Name" not in df.columns:
            df.columns = expected[:len(df.columns)]

    # Clean Full Name
    if "Full Name" in df.columns:
        df["Full Name"] = df["Full Name"].astype(str).str.strip().str.title()
        df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)
        df["Full Name"] = df["Full Name"].str.replace(r'[^A-Za-z\s\-\']', '', regex=True)

    # Clean Phone
    if "Phone Number" in df.columns:
        df["Phone Number"] = df["Phone Number"].astype(str).str.replace(r'\D', '', regex=True)
        # Ensure starts with 0 and 10 digits
        df["Phone Number"] = df["Phone Number"].apply(lambda x: x[-10:] if len(x) >= 10 else x)
        df["Phone Number"] = df["Phone Number"].apply(lambda x: '0' + x if not x.startswith('0') and len(x)==9 else x)

    # Clean Email
    if "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.strip().str.lower()
        df["Email"] = df["Email"].str.replace(' ', '').str.replace(',', '.')
        df["Email"] = df["Email"].str.replace(r'\.{2,}', '.', regex=True)

    # ---------- R FIX - SHOWS R 500.00 ----------
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

    if "Location" in df.columns:
        df["Location"] = df["Location"].astype(str).str.strip().str.title()

    # Remove duplicates
    df = df[df["Full Name"].astype(str).str.len() > 2]
    if "Full Name" in df.columns and "Phone Number" in df.columns:
        df = df.drop_duplicates(subset=["Full Name", "Phone Number"], keep='first')
    if "Email" in df.columns:
        df = df.drop_duplicates(subset=["Email"], keep='first')

    cleaned_count = len(df)
    removed = original_count - cleaned_count
    return df, original_count, cleaned_count, removed

# ---------- UI ----------
st.title("🧹 CleanData LAI - KZN Stock Cleaner")
st.caption("Fix messy customer lists in 2 seconds | R1500 lifetime")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if not USE_FIREBASE:
    st.warning("⚠️ You are in LOCAL mode - logins will be lost when app restarts! Add Firebase in Secrets to fix forever. (I will show you how)")

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
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
        if st.button("Create Account - 24hr Free Trial"):
            ok, msg = signup(email2, pwd2)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    st.stop()

# Logged in view
st.sidebar.write(f"✅ Logged: {st.session_state.user_email}")
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
            # PDF OCR
            pdf_bytes = uploaded.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            # Try to parse text to df - simple split
            lines = [l for l in text.split('\n') if l.strip()]
            # Fallback to OCR if no text
            if len(lines) < 3:
                # render as image and OCR
                pix = doc[0].get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img)
                lines = [l for l in text.split('\n') if l.strip()]
            # Make df from lines - assume comma separated
            data = [l.split(',') for l in lines]
            df = pd.DataFrame(data[1:], columns=data[0] if data else None)
        else:
            # Image OCR
            image = Image.open(uploaded)
            text = pytesseract.image_to_string(image)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            # Try to detect header
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
                st.success(f"Cleaned! Original: {orig} → Cleaned: {cleaned} | Removed duplicates/invalid: {removed}")
                st.write("Cleaned Data - FIXED NAMES & EMAILS & Rands")
                st.dataframe(cleaned_df)
                
                csv = cleaned_df.to_csv(index=False).encode('utf-8')
                st.download_button("⬇️ Download Clean CSV (Rands included)", csv, "cleaned_with_rands.csv", "text/csv")
    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)
