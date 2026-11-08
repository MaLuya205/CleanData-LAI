from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import sqlite3
import string
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st_canvas = None

# -----------------------------------------------------------------------------
# App configuration and design
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="CleanData LAI | Data workspace",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "CleanData LAI"
APP_DIR = Path(__file__).resolve().parent
# Streamlit Community Cloud has an ephemeral filesystem. This path is suitable for
# development and demos; configure a persistent database before storing real accounts.
DB_PATH = Path(os.getenv("CLEANDATA_DB", str(APP_DIR / "cleandata_users.sqlite3"))).expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
try:
    MAX_UPLOAD_MB = max(1, min(100, int(os.getenv("MAX_UPLOAD_MB", "25"))))
except (TypeError, ValueError):
    MAX_UPLOAD_MB = 25
OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 60

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --ink:#101828; --muted:#667085; --line:#e6eaf0; --mint:#14b88a; --navy:#101b32; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background:linear-gradient(180deg,#f7f9fc 0%,#f5f7fb 100%); color:var(--ink); }
    .block-container { max-width:1450px; padding-top:1.6rem; padding-bottom:3rem; }
    h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; color:#101828; }
    h1 { font-weight:800 !important; }
    [data-testid="stSidebar"] { background:#101b32; border-right:1px solid #26344d; }
    [data-testid="stSidebar"] * { color:#eef4ff !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:7px 10px; border-radius:9px; }
    [data-testid="stSidebar"] hr { border-color:#34425a; }
    div[data-testid="stMetric"] { background:white; border:1px solid var(--line); padding:17px 18px; border-radius:15px; box-shadow:0 5px 18px rgba(16,24,40,.035); }
    div[data-testid="stMetricLabel"] { color:#667085; font-weight:600; }
    div[data-testid="stMetricValue"] { color:#101828; font-family:'Manrope',sans-serif; font-weight:800; }
    .brandbar { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:16px 20px; margin-bottom:22px; background:#101b32; border:1px solid #25334d; border-radius:18px; color:#fff; box-shadow:0 12px 30px rgba(16,27,50,.12); }
    .brandname { font-family:'Manrope',sans-serif; font-size:21px; font-weight:800; letter-spacing:-.04em; }
    .brandname span { color:#35d6a6; }
    .brandtag { color:#c4cee0; font-size:12px; }
    .hero { padding:30px; border-radius:22px; color:white; background:radial-gradient(circle at 85% 10%,rgba(38,211,162,.24),transparent 28%),linear-gradient(125deg,#101b32,#1c3152); margin-bottom:22px; }
    .hero h1 { color:white !important; margin:0 0 8px 0; font-size:34px; }
    .hero p { color:#cbd6e7; margin:0; max-width:760px; }
    .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:10px; font-weight:800; color:#3ed9ad; margin-bottom:10px; }
    .panel { background:white; border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:0 5px 18px rgba(16,24,40,.035); }
    .muted { color:#667085; }
    .smallcaps { font-size:11px; text-transform:uppercase; letter-spacing:.1em; font-weight:700; color:#667085; }
    .stButton>button, .stDownloadButton>button { border-radius:10px; font-weight:700; min-height:42px; }
    .stButton>button[kind="primary"] { background:#12a981; border-color:#12a981; }
    div[data-testid="stFileUploader"] { background:white; border:1px dashed #b9c5d5; border-radius:14px; padding:8px; }
    .footer { color:#98a2b3; font-size:12px; text-align:center; padding:22px 0 4px; }
    </style>
    <div class="brandbar"><div><div class="brandname">CleanData <span>LAI</span> ✦</div><div class="brandtag">A cleaner workspace for better business decisions</div></div><div class="brandtag">SOUTH AFRICA · DATA WORKSPACE</div></div>
    """,
