import streamlit as st
import pandas as pd

st.set_page_config(page_title="CleanData Pro", layout="wide")

st.title("CleanData Pro - Data Cleaner for Businesses")
st.write("Upload messy Excel or CSV and get clean data. No Excel skills needed.")

dept = st.selectbox("Choose Department", ["Sales", "Customers", "Stock", "HR", "General"])

uploaded = st.file_uploader("Upload your file", type=["csv", "xlsx"])

if uploaded:
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
        
        st.subheader("Before Cleaning")
        st.dataframe(df.head())

        # Cleaning
        # 1. Trim spaces
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        
        # 2. Remove duplicates
        df = df.drop_duplicates()
        
        # 3. Fix empty and error values
        df = df.replace(["#DIV/0!", "#N/A", "#REF!", "#VALUE!", "nan", "None"], "")
        df = df.fillna("")

        st.subheader("After Cleaning - Ready to Use")
        st.dataframe(df.head())
        st.success(f"Cleaned {len(df)} rows. Duplicates removed and errors fixed.")

        # Download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Clean File", csv, "cleaned_data.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Please upload a file to start cleaning.")

st.sidebar.title("Rental Plans")
st.sidebar.write("Starter: R199/mo")
st.sidebar.write("Pro: R499/mo - Unlimited")
st.sidebar.write("Enterprise: R999/mo")
st.sidebar.write("Contact: MaLuya205")
