import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os, json

st.set_page_config(page_title="CleanData Pro", layout="wide")

TRIAL_FILE = "trials.json"

def load_trials():
    if os.path.exists(TRIAL_FILE):
        with open(TRIAL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_trials(data):
    with open(TRIAL_FILE, "w") as f:
        json.dump(data, f)

trials = load_trials()

# --- SIDEBAR LOGIN ---
st.sidebar.title("Business Login")
business_id = st.sidebar.text_input("Enter Business Email or Phone (for trial)")

if not business_id:
    st.title("CleanData Pro - Data Cleaner for Businesses")
    st.write("**Fix messy Excel in seconds. For Shops, Salons, Schools, Farms in KZN**")
    st.warning("👈 Enter your Business Email/Phone in the left sidebar to start your 1-Day FREE Trial")
    st.info("Trusted by local businesses - No Excel skills needed.")
    st.stop()

now = datetime.now()

if business_id not in trials:
    trials[business_id] = {
        "start": now.isoformat(),
        "expiry": (now + timedelta(days=1)).isoformat()
    }
    save_trials(trials)
    st.sidebar.success("🎉 1-Day FREE Trial Started!")

expiry = datetime.fromisoformat(trials[business_id]["expiry"])

if now > expiry:
    st.title("⏰ Trial Expired - Upgrade to Continue")
    st.error(f"Your free trial ended on {expiry.strftime('%Y-%m-%d %H:%M')}")
    st.markdown(f"""
    ### To Reactivate Your Account:
    **1. WhatsApp MaLuya:** 078 767 4535  
    **2. Pay & Send Proof**

    **Plans:**
    - Starter: **R199/mo** - 100 files
    - Pro: **R499/mo** - Unlimited (Most Popular)
    - Enterprise: **R999/mo** - All departments + Support

    Click below to pay or request bank details privately:
    """)
    st.link_button("📱 Chat on WhatsApp to Pay - 078 767 4535", "https://wa.me/27787674535?text=Hi%20MaLuya,%20my%20CleanData%20trial%20expired.%20Business%20ID:%20"+business_id+"%20I%20want%20to%20pay%20for%20Pro%20R499")
    st.write(f"Your Business ID: `{business_id}` (Send this on WhatsApp)")
    st.stop()
else:
    hours_left = int((expiry - now).total_seconds() / 3600)
    mins_left = int(((expiry - now).total_seconds() % 3600) / 60)
    st.sidebar.success(f"Trial: {hours_left}h {mins_left}m left")
    st.sidebar.write(f"Expires: {expiry.strftime('%Y-%m-%d %H:%M')}")
    st.sidebar.link_button("Need Help? WhatsApp Me", "https://wa.me/27787674535")

# --- MAIN APP ---
st.title("CleanData Pro - Data Cleaner for Businesses")
st.caption(f"Logged in as: {business_id} | Department Cleaner")
dept = st.selectbox("Choose Department", ["Sales", "Customers", "Stock", "HR", "General"])
uploaded = st.file_uploader("Upload your file", type=["csv", "xlsx"])

if uploaded:
    try:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.subheader("Before Cleaning")
        st.dataframe(df.head())
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df = df.drop_duplicates()
        df = df.replace(["#DIV/0!", "#N/A", "#REF!", "#VALUE!", "nan", "None"], "")
        df = df.fillna("")
        st.subheader("After Cleaning")
        st.dataframe(df.head())
        st.success(f"Cleaned {len(df)} rows for {dept}!")
        st.download_button("⬇️ Download Clean File", df.to_csv(index=False).encode('utf-8'), "cleaned_data.csv", "text/csv")
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload a file to start cleaning.")

st.sidebar.markdown("---")
st.sidebar.title("After Trial Pricing")
st.sidebar.write("R199 Starter | R499 Pro | R999 Enterprise")
st.sidebar.write("📱 078 767 4535")
