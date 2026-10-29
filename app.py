import streamlit as st
import pandas as pd
import re
import time
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# --- SAFE IMPORTS FOR PDF AND IMAGES (Won't crash) ---
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except:
    HAS_OCR = False

# --- PAGE CONFIG ---
st.set_page_config(page_title="CleanData LAI - Data Cleaning", page_icon="🧹", layout="wide")

# --- EMAIL CONFIG ---
try:
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PASS = st.secrets["EMAIL_PASS"]
except:
    EMAIL_USER = None
    EMAIL_PASS = None

def send_email_code(to_email, code):
    if not EMAIL_USER or not EMAIL_PASS:
        return False, "Email not configured in Secrets"
    try:
        msg = MIMEText(f"Your CleanData LAI verification code is: {code}\n\nValid for 10 minutes.\n\nLuya Store - CleanData LAI")
        msg['Subject'] = f"Your CleanData Code: {code}"
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True, "Sent"
    except Exception as e:
        return False, str(e)

# --- FILE READER FOR ALL TYPES ---
def read_any_file(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        # CSV
        if name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        # Excel
        elif name.endswith(('.xlsx', '.xls')):
            return pd.read_excel(uploaded_file)
        # PDF
        elif name.endswith('.pdf'):
            if not HAS_PYMUPDF:
                st.error("PDF module still installing, please wait 2 min and refresh")
                return None
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            # Try to parse as table - split by lines
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if len(lines) > 1:
                # Try to detect if comma separated
                data = []
                for line in lines:
                    if ',' in line:
                        data.append([x.strip() for x in line.split(',')])
                    else:
                        data.append(line.split())
                # Make DataFrame
                if data:
                    max_cols = max(len(r) for r in data)
                    # First row as header if looks like header
                    return pd.DataFrame(data[1:], columns=data[0] if len(data[0])==max_cols else None)
            st.write("PDF Text Preview:")
            st.text(text[:2000])
            return pd.DataFrame({"pdf_text": lines})
        # Image JPG/PNG
        elif name.endswith(('.png', '.jpg', '.jpeg')):
            if not HAS_OCR:
                st.error("Image OCR still installing, wait 2 min")
                return None
            image = Image.open(uploaded_file)
            text = pytesseract.image_to_string(image)
            st.write("Image Text Found:")
            st.text(text[:2000])
            lines = [line for line in text.split('\n') if line.strip()]
            data = []
            for line in lines:
                # Split by multiple spaces or comma
                parts = re.split(r'\s{2,}|,', line)
                parts = [p.strip() for p in parts if p.strip()]
                if parts:
                    data.append(parts)
            if data:
                return pd.DataFrame(data[1:], columns=data[0] if len(data[0])>1 else None)
            return pd.DataFrame({"image_text": lines})
        else:
            st.error("Upload CSV, XLSX, PDF, JPG, PNG only")
            return None
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# --- DATA CLEANING LOGIC ---
def clean_dataframe(df):
    if df is None or df.empty:
        return df
    original_rows = len(df)
    # 1. Trim spaces
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    # 2. Lowercase for emails, standard case for names
    for col in df.columns:
        col_lower = str(col).lower()
        if 'email' in col_lower:
            df[col] = df[col].astype(str).str.lower().str.strip()
        if 'name' in col_lower or 'dept' in col_lower or 'department' in col_lower:
            df[col] = df[col].astype(str).str.title().str.strip()
    # 3. Clean phone
    for col in df.columns:
        if 'phone' in str(col).lower():
            df[col] = df[col].astype(str).str.replace(r'[^0-9]', '', regex=True)
    # 4. Remove duplicates
    df_cleaned = df.drop_duplicates()
    # 5. Remove invalid emails
    for col in df.columns:
        if 'email' in str(col).lower():
            df_cleaned = df_cleaned[df_cleaned[col].str.contains('@', na=False)]
            df_cleaned = df_cleaned[df_cleaned[col].str.contains(r'\.', na=False)]
    
    removed = original_rows - len(df_cleaned)
    return df_cleaned, removed, original_rows

# --- AUTH SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'users' not in st.session_state:
    st.session_state.users = {}
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Sidebar
with st.sidebar:
    st.title("🧹 CleanData LAI")
    if st.session_state.logged_in:
        st.success(f"Welcome {st.session_state.current_user}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    else:
        st.info("Login to clean data")

# --- MAIN APP ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            if email in st.session_state.users and st.session_state.users[email]['password'] == pwd:
                st.session_state.logged_in = True
                st.session_state.current_user = email
                st.session_state.users[email]['login_time'] = datetime.now()
                st.success("Logged in!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Wrong email or password")
    
    with tab2:
        st.subheader("Create Account & Get Code")
        new_email = st.text_input("Your Email", key="new_email")
        new_pwd = st.text_input("Create Password", type="password", key="new_pwd")
        company = st.text_input("Company Name", key="company")
        if st.button("Create Account & Send Code"):
            if new_email and new_pwd:
                code = str(random.randint(100000, 999999))
                st.session_state.users[new_email] = {
                    'password': new_pwd,
                    'company': company,
                    'code': code,
                    'verified': False,
                    'login_time': datetime.now()
                }
                success, msg = send_email_code(new_email, code)
                if success:
                    st.success(f"Code sent to {new_email}! Check inbox & spam!")
                    st.session_state.pending_email = new_email
                else:
                    st.error(f"Email failed: {msg} - Your code is: {code} (for testing)")
                    st.session_state.pending_email = new_email
            else:
                st.error("Fill email and password")
        
        if 'pending_email' in st.session_state:
            st.divider()
            st.subheader(f"Enter Code sent to {st.session_state.pending_email}")
            code_input = st.text_input("6-digit code")
            if st.button("Verify Code"):
                pend = st.session_state.pending_email
                if pend in st.session_state.users and st.session_state.users[pend]['code'] == code_input:
                    st.session_state.users[pend]['verified'] = True
                    st.session_state.logged_in = True
                    st.session_state.current_user = pend
                    st.success("Verified! Welcome!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Wrong code")

else:
    # LOGGED IN - MAIN CLEANING APP
    user_data = st.session_state.users.get(st.session_state.current_user, {})
    login_time = user_data.get('login_time', datetime.now())
    trial_end = login_time + timedelta(hours=24)
    remaining = trial_end - datetime.now()
    
    if remaining.total_seconds() > 0:
        hours = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        st.success(f"Welcome {st.session_state.current_user} - {user_data.get('company','Luya Store')} ✅ | Trial: {hours}h {mins}m left")
    else:
        st.error("Trial expired! Contact Luyanda for R1500 lifetime")
        st.stop()
    
    st.title("🧹 CleanData LAI - Upload & Clean")
    st.write("Supports: CSV, XLSX, PDF, JPG, PNG - 200 MB per file")
    
    uploaded = st.file_uploader("Choose file", type=['csv','xlsx','xls','pdf','png','jpg','jpeg'])
    
    if uploaded:
        st.info(f"File: {uploaded.name} - {uploaded.size} bytes")
        df = read_any_file(uploaded)
        if df is not None and not df.empty:
            st.subheader("Original Data Preview")
            st.dataframe(df.head(20))
            st.write(f"Rows: {len(df)} | Columns: {list(df.columns)}")
            
            if st.button("🧹 Clean Data Now"):
                cleaned, removed, original = clean_dataframe(df)
                st.success(f"Cleaned! Original: {original} rows → Cleaned: {len(cleaned)} rows | Removed duplicates/invalid: {removed}")
                st.subheader("Cleaned Data")
                st.dataframe(cleaned.head(20))
                
                # Download
                csv = cleaned.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Cleaned CSV", csv, "cleaned_data.csv", "text/csv")
    else:
        st.info("👆 Upload a file to start cleaning - Try with the image you have!")
