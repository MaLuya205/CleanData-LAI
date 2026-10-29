import streamlit as st
import pandas as pd
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from datetime import datetime, timedelta

# ---------- CONFIG ----------
st.set_page_config(page_title="CleanData LAI - KZN", layout="wide")

# ---------- SIMPLE PERSISTENT AUTH USING FIRESTORE / SESSION ----------
# We will store users in a file that persists on Streamlit Cloud using st.secrets or local json
# For now, using a JSON file + Firebase style check
import json, os
USERS_FILE = "users_db.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def email_exists(email):
    users = load_users()
    return email.lower() in users

# ---------- AUTH FUNCTIONS ----------
def signup(email, password):
    email = email.lower().strip()
    users = load_users()
    
    if email in users:
        return False, "❌ User already exists! This email already has an account. Please Login."
    
    users[email] = {
        "password": password,
        "created_at": datetime.now().isoformat(),
        "trial_expires": (datetime.now() + timedelta(hours=24)).isoformat()
    }
    save_users(users)
    return True, "✅ Account created! 24hr free trial started!"

def login(email, password):
    email = email.lower().strip()
    users = load_users()
    
    if email not in users:
        return False, "❌ Email not found. Please sign up first."
    
    if users[email]["password"] != password:
        return False, "❌ Wrong password. Try again."
    
    # Check trial
    expires = datetime.fromisoformat(users[email]["trial_expires"])
    if datetime.now() > expires:
        return False, "❌ Your 24hr trial expired. Please pay R1500 to continue."
    
    return True, "✅ Login successful!"

# ---------- CLEANING LOGIC - FIXED R ----------
def clean_data(df):
    original_count = len(df)
    
    # Drop empty rows
    df = df.dropna(how='all')
    df = df[~df.astype(str).apply(lambda x: x.str.contains('#ERROR|N/A', na=False)).any(axis=1)]
    
    # Standardize columns
    df.columns = [c.strip() for c in df.columns]
    if len(df.columns) >= 6:
        df.columns = ["Full Name", "Phone Number", "Email", "Amount (R)", "Location", "Date"][:len(df.columns)]
    
    # Clean Full Name - Title Case
    if "Full Name" in df.columns:
        df["Full Name"] = df["Full Name"].astype(str).str.strip().str.title()
        df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)
    
    # Clean Phone - only digits, 10 digits
    if "Phone Number" in df.columns:
        df["Phone Number"] = df["Phone Number"].astype(str).str.replace(r'\D', '', regex=True)
        df["Phone Number"] = df["Phone Number"].str.replace(r'^0+', '0', regex=True)
    
    # Clean Email - lower case
    if "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.strip().str.lower()
        df["Email"] = df["Email"].str.replace(' ', '')
        df["Email"] = df["Email"].str.replace(r',', '.', regex=False)
    
    # ---------- R FIX - THIS IS WHAT YOU ASKED FOR BRO ----------
    if "Amount (R)" in df.columns:
        # Remove commas first
        df["Amount (R)"] = df["Amount (R)"].astype(str).str.replace(',', '', regex=False)
        # Extract number
        df["Amount (R)"] = df["Amount (R)"].str.extract(r'(\d+\.?\d*)')[0]
        # Format as R xxx.xx - CLEAR FOR CUSTOMER!
        def format_r(x):
            if pd.isna(x) or str(x).strip() == "":
                return ""
            try:
                return f"R {float(x):.2f}"
            except:
                return ""
        df["Amount (R)"] = df["Amount (R)"].apply(format_r)
    
    # Clean Location
    if "Location" in df.columns:
        df["Location"] = df["Location"].astype(str).str.strip().str.title()
    
    # Remove duplicates based on Full Name + Phone
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["Full Name", "Phone Number"], keep='first')
    df = df.drop_duplicates(subset=["Email"], keep='first')
    
    cleaned_count = len(df)
    removed = original_count - cleaned_count
    
    return df, original_count, cleaned_count, removed

# ---------- UI ----------
st.title("🧹 CleanData LAI - KZN Stock Cleaner")

# Session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# Auth Tabs
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
                st.info("Now go to Login tab and login!")
            else:
                st.error(msg)
    st.stop()

# Logged in view
st.sidebar.write(f"Logged as: {st.session_state.user_email}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

uploaded = st.file_uploader("Upload messy CSV, Excel or Image (JPG/PNG/PDF)", type=["csv","xlsx","xls","jpg","jpeg","png","pdf"])

if uploaded:
    # ... your existing file reading code here ...
    # (keep your fitz and pytesseract logic)
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        elif uploaded.name.endswith((".xlsx","xls")):
            df = pd.read_excel(uploaded)
        else:
            # Image/PDF OCR - your existing code
            st.info("Image/PDF detected - using OCR")
            # ... keep your OCR code ...
            df = pd.DataFrame() # placeholder
        
        if not df.empty:
            st.write("Original Preview:")
            st.dataframe(df.head())
            
            if st.button("Clean Data Now - Excel Formulas"):
                cleaned_df, orig, cleaned, removed = clean_data(df)
                st.success(f"Cleaned! Original: {orig} → Cleaned: {cleaned} | Removed duplicates/invalid: {removed}")
                st.write("Cleaned Data - FIXED NAMES & EMAILS")
                st.dataframe(cleaned_df)
                
                csv = cleaned_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Clean CSV", csv, "cleaned.csv", "text/csv")
    except Exception as e:
        st.error(f"Error: {e}")
