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

def read_any_file(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif name.endswith(('.xlsx','.xls')):
            return pd.read_excel(uploaded_file)
        elif name.endswith('.pdf'):
            if not HAS_PYMUPDF:
                st.error("PDF library loading, try again in 1 min")
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
                st.error("OCR loading, try again in 1 min")
                return None
            image = Image.open(uploaded_file)
            image = image.convert('L')
            w, h = image.size
            image = image.resize((w*2, h*2))
            text = pytesseract.image_to_string(image)
            st.text(text[:3000])
            
            lines = [l for l in text.split('\n') if l.strip()]
            cleaned_lines = []
            for l in lines:
                if any(x in l for x in ['NOTES','Total collected','KWAMASHU GENERAL','Date: 15','Book No','Full Name','---','PLEASE CLEAN']):
                    continue
                if len(l.strip()) < 5:
                    continue
                cleaned_lines.append(l)
            
            data = []
            for l in cleaned_lines:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', l)
                phone_match = re.search(r'0\d{2}[\s\-]*\d{3}[\s\-]*\d{4}', l)
                email = email_match.group(0) if email_match else ""
                phone = phone_match.group(0) if phone_match else ""
                
                if phone_match:
                    name_part = l[:phone_match.start()].strip()
                elif email_match:
                    name_part = l[:email_match.start()].strip()
                else:
                    name_part = " ".join(l.split()[0:2])
                
                parts = re.split(r'\s{2,}', l)
                row = [name_part, phone, email, l, "", ""]
                if len(parts) >= 4:
                    row = parts[:6] + [""]*(6-len(parts))
                
                data.append(row[:6])
            
            df = pd.DataFrame(data, columns=["Full Name","Phone","Email","Amount","Location","Date"])
            return df
        else:
            st.error("Use CSV, XLSX, PDF, JPG, PNG")
            return None
    except Exception as e:
        st.error(f"Read error: {e}")
        return None

def clean_dataframe(df):
    if df is None or df.empty:
        return df, 0, 0
    
    orig = len(df)
    
    if len(df.columns) > 6:
        df = df.iloc[:, :6]
    
    if len(df.columns) == 6:
        df.columns = ["Full Name", "Phone", "Email", "Amount", "Location", "Date"]
    elif len(df.columns) >= 4:
        cols = list(df.columns)
        df.columns = ["Full Name", "Phone", "Email", "Amount", "Location", "Date"][:len(cols)]
    
    df = df[~df["Full Name"].astype(str).str.contains("Full Name", na=False)]
    
    for col in df.columns:
        df[col] = df[col].astype(str).apply(lambda x: re.sub(r'\s+', ' ', x).strip())
    
    if "Full Name" in df.columns:
        df["Full Name"] = df["Full Name"].astype(str).str.lower().str.title()
        df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)
        df = df[~df["Full Name"].str.contains(r'^#ERROR|N/A|^Test@|^$|^\s*$', na=False, case=False)]
        df = df[df["Full Name"].str.len() > 2]
    
    if "Phone" in df.columns:
        df["Phone"] = df["Phone"].astype(str).str.replace(r'[^0-9]', '', regex=True)
    
    if "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.lower().str.strip()
        df["Email"] = df["Email"].str.replace(r'\.\.+', '.', regex=True)
        df["Email"] = df["Email"].str.replace(r'\s+', '', regex=True)
        df["Email"] = df["Email"].str.replace(r',', '.', regex=False)
        df = df[df["Email"].str.contains('@', na=False)]
        df = df[df["Email"].str.contains(r'\.', na=False)]
        df = df[~df["Email"].str.contains(r'@nene$|@zwane$|@\s*$|^musa$|^test', na=False)]
    
    if "Location" in df.columns:
        df["Location"] = df["Location"].astype(str).str.lower().str.title()
        df["Location"] = df["Location"].str.replace(r'\s+', ' ', regex=True)
    
    if "Amount" in df.columns:
        df["Amount"] = df["Amount"].astype(str).str.replace(r'R|\s', '', regex=True).str.replace(',', '', regex=False)
        df["Amount"] = df["Amount"].str.replace(r'[^0-9.]', '', regex=True)
    
    df['_dup_key'] = df["Full Name"].astype(str).str.lower() + "_" + df["Phone"].astype(str)
    df = df.drop_duplicates(subset=['_dup_key'], keep='first')
    df = df.drop(columns=['_dup_key'])
    df = df.drop_duplicates()
    
    cleaned = len(df)
    removed = orig - cleaned
    return df, removed, orig

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
                    st.warning(f"Code for testing: {code}")
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
            st.write(f"Rows: {len(df)}")
            if st.button("🧹 Clean Data Now - Excel Formulas"):
                cleaned, removed, original = clean_dataframe(df)
                st.success(f"Cleaned! Original: {original} → Cleaned: {len(cleaned)} | Removed duplicates/invalid: {removed}")
                st.subheader("Cleaned Data - FIXED NAMES & EMAILS")
                st.dataframe(cleaned)
                csv = cleaned.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Cleaned CSV", csv, "cleaned_data.csv", "text/csv")
