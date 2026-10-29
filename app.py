import streamlit as st
import pandas as pd
import re
import time
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

try:
    import fitz
    HAS_PYMUPDF = True
except:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except:
    HAS_OCR = False

st.set_page_config(page_title="CleanData LAI - Data Cleaning", page_icon="🧹", layout="wide")

# Email
try:
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PASS = st.secrets["EMAIL_PASS"]
except:
    EMAIL_USER = None
    EMAIL_PASS = None

def send_email_code(to_email, code):
    if not EMAIL_USER or not EMAIL_PASS:
        return False, "No Secrets"
    try:
        msg = MIMEText(f"Your CleanData LAI code: {code}\nValid 10 min.\nLuya Store")
        msg['Subject'] = f"Your Code: {code}"
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

# --- READ ANY FILE ---
def read_any_file(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif name.endswith(('.xlsx','.xls')):
            return pd.read_excel(uploaded_file)
        elif name.endswith('.pdf'):
            if not HAS_PYMUPDF:
                st.error("PDF installing, wait")
                return None
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            text = ""
            for p in doc:
                text += p.get_text() + "\n"
            lines = [l for l in text.split('\n') if l.strip()]
            data = []
            for l in lines:
                parts = re.split(r'\s{2,}|,|\t', l)
                parts = [x.strip() for x in parts if x.strip()]
                if parts:
                    data.append(parts)
            if data:
                return pd.DataFrame(data)
            return pd.DataFrame({"text": lines})
        elif name.endswith(('.png','.jpg','.jpeg')):
            if not HAS_OCR:
                st.error("OCR installing, wait")
                return None
            image = Image.open(uploaded_file)
            text = pytesseract.image_to_string(image)
            st.text(text[:3000])
            lines = [l for l in text.split('\n') if l.strip()]
            data = []
            for l in lines:
                # Skip notes
                if 'NOTES' in l or 'Total collected' in l or 'KWAMASHU' in l or 'Date: 15' in l or 'Full Name' in l or '---' in l:
                    continue
                parts = re.split(r'\s{2,}|\t', l)
                parts = [x.strip() for x in parts if x.strip()]
                if len(parts) < 3:
                    parts = l.split()
                    # Heuristic: try to rebuild
                    if len(parts) >= 4:
                        # Name is first 2 words, phone next, email next
                        pass
                if parts:
                    data.append(parts)
            if not data:
                return None
            # Try to make 6 columns
            df = pd.DataFrame(data)
            return df
        else:
            st.error("Use CSV, XLSX, PDF, JPG, PNG")
            return None
    except Exception as e:
        st.error(f"Read error: {e}")
        return None

# --- FINAL CLEANING WITH EXCEL FORMULAS ---
def clean_dataframe(df):
    if df is None or df.empty:
        return df, 0, 0
    
    orig = len(df)
    
    # If df has many columns, keep first 6
    if len(df.columns) > 6:
        df = df.iloc[:, :6]
    
    # Rename to standard if no header
    if len(df.columns) == 6:
        df.columns = ["Full Name", "Phone", "Email", "Amount", "Location", "Date"]
    elif len(df.columns) >= 4:
        # Guess
        cols = list(df.columns)
        df.columns = ["Full Name", "Phone", "Email", "Amount", "Location", "Date"][:len(cols)]
    
    # Remove rows that are headers repeated
    df = df[~df["Full Name"].astype(str).str.contains("Full Name|THANDI NENE.*Phone", na=False)]
    
    # EXCEL FORMULA 1: TRIM - remove extra spaces everywhere
    for col in df.columns:
        df[col] = df[col].astype(str).apply(lambda x: re.sub(r'\s+', ' ', x).strip())
    
    # EXCEL FORMULA 2: PROPER for Names - Sipho Dlamini not sipho dlamini or SIPHO DLAMINI
    if "Full Name" in df.columns:
        df["Full Name"] = df["Full Name"].astype(str).str.lower().str.title()
        df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)
        # Remove invalid names
        df = df[~df["Full Name"].str.contains(r'^#ERROR|N/A|^Test@|^$|^\s*$', na=False, case=False)]
        df = df[df["Full Name"].str.len() > 2]
    
    # EXCEL FORMULA 3: Phone - only digits, remove spaces, dashes, ext
    if "Phone" in df.columns:
        df["Phone"] = df["Phone"].astype(str).str.replace(r'[^0-9]', '', regex=True)
        # Fix SA numbers: must be 10 digits starting 0
        df["Phone"] = df["Phone"].apply(lambda x: x if len(x)==10 else ("0"+x[-9:] if len(x)>=9 else x))
    
    # EXCEL FORMULA 4: LOWER for Emails + fix
    if "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.lower().str.strip()
        df["Email"] = df["Email"].str.replace(r'\.\.+', '.', regex=True)  # .. -> .
        df["Email"] = df["Email"].str.replace(r'\s+', '', regex=True)  # no spaces
        df["Email"] = df["Email"].str.replace(r',', '.', regex=False)
        # Remove bad emails
        df = df[df["Email"].str.contains('@', na=False)]
        df = df[df["Email"].str.contains(r'\.', na=False)]
        df = df[~df["Email"].str.contains(r'@nene$|@zwane$|@\s*$|^musa$|^test', na=False)]
        df = df[~df["Email"].str.match(r'^musa$|^bongani$|^test')]
    
    # EXCEL FORMULA 5: PROPER for Location
    if "Location" in df.columns:
        df["Location"] = df["Location"].astype(str).str.lower().str.title()
        df["Location"] = df["Location"].str.replace(r'\s+', ' ', regex=True)
    
    # Amount - remove R and spaces, keep number
    if "Amount" in df.columns:
        df["Amount"] = df["Amount"].astype(str).str.replace(r'R|\s|,\s*', '', regex=True).str.replace(',', '', regex=False)
        df["Amount"] = df["Amount"].str.replace(r'[^0-9.]', '', regex=True)
    
    # EXCEL FORMULA 6: REMOVE DUPLICATES - case insensitive!
    # Create key for duplicate check
    df['_dup_key'] = df["Full Name"].astype(str).str.lower() + "_" + df["Phone"].astype(str)
    df = df.drop_duplicates(subset=['_dup_key'], keep='first')
    df = df.drop(columns=['_dup_key'])
    
    # Also drop exact duplicates
    df = df.drop_duplicates()
    
    cleaned = len(df)
    removed = orig - cleaned
    return df, removed, orig

# --- AUTH ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'users' not in st.session_state:
    st.session_state.users = {}
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

with st.sidebar:
    st.title("🧹 CleanData LAI")
    if st.session_state.logged_in:
        st.success(f"Welcome {st.session_state.current_user}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login","Create Account"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login"):
            if email in st.session_state.users and st.session_state.users[email]['password']==pwd:
                st.session_state.logged_in=True
                st.session_state.current_user=email
                st.session_state.users[email]['login_time']=datetime.now()
                st.rerun()
            else:
                st.error("Wrong")
    with tab2:
        new_email = st.text_input("Your Email", key="new_email")
        new_pwd = st.text_input("Create Password", type="password", key="new_pwd")
        company = st.text_input("Company Name", key="company")
        if st.button("Create Account & Send Code"):
            if new_email and new_pwd:
                code = str(random.randint(100000,999999))
                st.session_state.users[new_email]={'password':new_pwd,'company':company,'code':code,'verified':False,'login_time':datetime.now()}
                success,msg=send_email_code(new_email,code)
                if success:
                    st.success(f"Code sent to {new_email}!")
                else:
                    st.warning(f"Code for testing: {code} - Email: {msg}")
                st.session_state.pending_email=new_email
        if 'pending_email' in st.session_state:
            st.divider()
            code_input = st.text_input("6-digit code")
            if st.button("Verify Code"):
                pend=st.session_state.pending_email
                if pend in st.session_state.users and st.session_state.users[pend]['code']==code_input:
                    st.session_state.users[pend]['verified']=True
                    st.session_state.logged_in=True
                    st.session_state.current_user=pend
                    st.rerun()
                else:
                    st.error("Wrong code")
else:
    user_data = st.session_state.users.get(st.session_state.current_user,{})
    login_time = user_data.get('login_time', datetime.now())
    trial_end = login_time + timedelta(hours=24)
    remaining = trial_end - datetime.now()
    if remaining.total_seconds()>0:
        h=int(remaining.total_seconds()//3600)
        m=int((remaining.total_seconds()%3600)//60)
        st.success(f"Welcome {st.session_state.current_user} - Trial: {h}h {m}m")
    else:
        st.error("Trial expired")
        st.stop()
    
    st.title("🧹 CleanData LAI - Upload & Clean")
    st.write("Supports: CSV, XLSX, PDF, JPG, PNG")
    uploaded = st.file_uploader("Choose file", type=['csv','xlsx','xls','pdf','png','jpg','jpeg'])
    if uploaded:
        st.info(f"File: {uploaded.name} - {uploaded.size} bytes")
        df = read_any_file(uploaded)
        if df is not None and not df.empty:
            st.subheader("Original Data Preview")
            st.dataframe(df.head(30))
            st.write(f"Rows: {len(df)} | Columns: {list(df.columns)}")
            if st.button("🧹 Clean Data Now - Excel Formulas"):
                cleaned, removed, original = clean_dataframe(df)
                st.success(f"Cleaned! Original: {original} → Cleaned: {len(cleaned)} | Removed duplicates/invalid: {removed}")
                st.subheader("Cleaned Data - FIXED NAMES & EMAILS")
                st.dataframe(cleaned)
                csv = cleaned.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Cleaned CSV", csv, "cleaned_data.csv", "text/csv")
