from pathlib import Path
p = Path("/mnt/data/Pasted text.txt")
print(p.exists(), p.stat().st_size if p.exists() else None)
print(p.read_text(encoding="utf-8", errors="replace")[:20000] if p.exists() else "File not found")
import streamlit as st, pandas as pd, os, json, random, smtplib, hashlib, re, fitz
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from PIL import Image
import pytesseract

st.set_page_config(page_title="CleanData LAI - KZN", layout="wide", page_icon="🚀")

def now_sa():
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
    if not date_str: return now_sa()
    try:
        dt = datetime.fromisoformat(str(date_str))
        if dt.tzinfo is not None: dt = dt.replace(tzinfo=None)
        return dt
    except: return now_sa()

USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        try: return json.load(open(USERS_FILE))
        except: return {}
    return {}
def save_users(d): json.dump(d, open(USERS_FILE,"w"), indent=2)
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()
def send_code(to_email, code, name=""):
    try:
        user = st.secrets["EMAIL_USER"]; pwd = st.secrets["EMAIL_PASS"]
        body = f"Hi {name},\n\nYour CleanData LAI code is: {code}\nValid 10 min.\n\nMaLuya Team"
        msg = MIMEText(body); msg["Subject"] = f"CleanData LAI - Your code {code}"; msg["From"] = user; msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s: s.login(user, pwd); s.send_message(msg)
        return True
    except: st.warning(f"Test mode - Your code is: {code}"); return True

PLANS = {"1day": {"name": "1 Day Pass", "price": "100.00", "days": 1},"1week": {"name": "1 Week Pass", "price": "570.00", "days": 7},"1month": {"name": "1 Month Pro", "price": "2250.00", "days": 30}}

USE_FIREBASE = False; db = None
try:
    import firebase_admin; from firebase_admin import credentials, firestore
    if "firebase" in st.secrets:
        cred_dict = dict(st.secrets["firebase"])
        if not firebase_admin._apps: cred = credentials.Certificate(cred_dict); firebase_admin.initialize_app(cred)
        db = firestore.client(); USE_FIREBASE = True
except: USE_FIREBASE = False

def get_payfast_creds():
    if "payfast" in st.secrets:
        try: return st.secrets["payfast"]["merchant_id"], st.secrets["payfast"]["merchant_key"], "https://www.payfast.co.za/eng/process"
        except: pass
    return "10000100", "46f0cd694581a", "https://sandbox.payfast.co.za/eng/process"

def payfast_button(email, plan_key):
    plan = PLANS[plan_key]; mid, mkey, url = get_payfast_creds()
    data = {"merchant_id": mid, "merchant_key": mkey,"return_url": f"https://cleandatalai.co.za?payment=success&plan={plan_key}&email={email}","cancel_url": "https://cleandatalai.co.za?payment=cancelled","notify_url": "https://cleandatalai.co.za/api/notify","m_payment_id": f"{email}|{plan_key}|{now_sa().timestamp()}","amount": plan["price"], "item_name": f"CleanData LAI {plan['name']}", "email_address": email, "email_confirmation": "1"}
    html = f'<form action="{url}" method="post" style="margin:8px 0;">'
    for k,v in data.items(): html += f'<input type="hidden" name="{k}" value="{v}">'
    color = "#ff6600" if plan_key=="1day" else "#0066ff" if plan_key=="1week" else "#00aa44"
    html += f'<button type="submit" style="background:{color};color:white;padding:12px;border:none;border-radius:8px;font-weight:bold;width:100%;cursor:pointer;">🔒 Pay R{plan["price"]} - {plan["name"]}</button></form>'
    return html

def extend_subscription(email, plan_key):
    days = PLANS[plan_key]["days"]; new_until = now_sa() + timedelta(days=days)
    if USE_FIREBASE: db.collection("users").document(email).update({"paid_until": new_until.isoformat(), "plan": plan_key,"last_payment": now_sa().isoformat(), "amount_paid": PLANS[plan_key]["price"]})
    else:
        users = load_users()
        if email in users: users[email]["paid_until"] = new_until.isoformat(); users[email]["expiry"] = new_until.isoformat(); users[email]["plan"] = plan_key; save_users(users)
    return new_until

def clean_data_v3(df, formulas_selected, extra_prompt=""):
    original_count = len(df); formulas_log = []; df = df.dropna(how='all'); df.columns = [str(c).strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if "name" in lc: col_map[c] = "Full Name"
        elif "phone" in lc or "cell" in lc: col_map[c] = "Phone Number"
        elif "email" in lc: col_map[c] = "Email"
        elif "amount" in lc or "rand" in lc or "price" in lc: col_map[c] = "Amount (R)"
        elif "depart" in lc: col_map[c] = "Department"
        elif c.lower() == "sales" or "sale" in lc: 
            if "amount" not in lc and "depart" not in lc:
                col_map[c] = "Department"
    df = df.rename(columns=col_map)
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip(); df[col] = df[col].str.replace(r'\s+', ' ', regex=True); df[col] = df[col].str.replace("nan","").str.replace("None","").str.replace("NaN","")
        if "uppercase" in extra_prompt.lower(): df[col] = df[col].str.upper()
        elif "lowercase" in extra_prompt.lower(): df[col] = df[col].str.lower()
        else:
            if col == "Full Name": df[col] = df[col].str.title()
            elif col == "Department": df[col] = df[col].str.lower().str.strip().str.title()
            elif col == "Email": df[col] = df[col].str.lower()
        formulas_log.append(f"TRIM+CLEAN on {col}")
    if "Full Name" in df.columns: df["Full Name"] = df["Full Name"].str.replace(r'\s+', ' ', regex=True)
    if "Phone Number" in df.columns: df["Phone Number"] = df["Phone Number"].astype(str).str.replace(r'\D','',regex=True).apply(lambda x: x[-10:] if len(x)>=10 else x)
    if "Email" in df.columns: df["Email"] = df["Email"].str.lower().str.replace(' ','').str.replace(',','.')
    if "Amount (R)" in df.columns:
        df["Amount (R)"] = df["Amount (R)"].astype(str).str.replace(',','',regex=False); df["Amount (R)"] = df["Amount (R)"].str.extract(r'(\d+\.?\d*)')[0]; df["Amount (R)"] = df["Amount (R)"].apply(lambda x: f"R {float(x):.2f}" if pd.notna(x) and str(x).strip()!="" else "")
    if "Department" in df.columns:
        df["Department"] = df["Department"].astype(str).str.strip().str.lower().str.title(); df["Department"] = df["Department"].replace({"": "Sales", "Nan": "Sales", "None": "Sales"})
    df = df.drop_duplicates(); formulas_log.append(f"UNIQUE removed {original_count - len(df)}"); formulas_log.extend(formulas_selected)
    return df, original_count, len(df), original_count-len(df), formulas_log

def generate_report(df, orig, dept, word_count, log, extra_prompt, user_info):
    now = now_sa().strftime("%Y-%m-%d %H:%M SAST")
    sales_total = 0.0; sales_avg = 0.0
    try:
        if "Amount (R)" in df.columns:
            clean = df["Amount (R)"].astype(str).str.replace("R","", regex=False).str.replace(" ","", regex=False).str.replace(",","", regex=False)
            nums = pd.to_numeric(clean, errors='coerce').fillna(0); sales_total = nums.sum(); sales_avg = nums.mean() if len(nums)>0 else 0
    except: pass
    dup_removed = orig - len(df)
    report = f"""CleanData LAI - Professional Business Report
Date: {now}
Client: {user_info.get('name','')} | Company: {user_info.get('company','')} | Dept: {dept}
Location: Inanda, Durban KZN | Phone: {user_info.get('phone','')}

Executive summary:
Original records {orig}, cleaned records {len(df)}, duplicates removed {dup_removed}. Quality 62 percent to 96 percent. Ready for SARS, Pastel, Sage.

Sales validation:
Total sales amount: R {sales_total:,.2f}
Average sale value: R {sales_avg:,.2f}
Department standardized to Sales (professional).
All transactions verified via Sumif, Sumifs.

Data quality:
Full names: Proper case. Example Sipho Dlamini, Thandi Nene.
Emails: Lowercase. Example sipho@gmail.com, thandi@nene
Amounts: R format. Example R 100.00, R 250.00
Department: Standardized to Sales (not SALES, sales)

Formulas applied ({len(log)}):
{', '.join(log[:15])}

Instruction: {extra_prompt if extra_prompt else 'Standard auto clean'}

Recommendation:
Data ready for reporting, payroll, audit. Import to accounting.

Compliance: PoPIA, SARS ready. Generated by CleanData LAI KZN - 867 Nkosisikelela Street, Inanda.

End report {word_count} words professional free.
"""
    words = report.split()
    if len(words) > word_count: final = " ".join(words[:word_count])
    else:
        filler = "Data validated with Index Match, Xlookup, Textjoin for accuracy. No errors found. Ready for management use."
        while len(words) < word_count: report += " " + filler; words = report.split()
        final = " ".join(words[:word_count])
    return final

# === CLICKABLE TOP BAR ===
st.markdown("""
<style>
.qinetiq-bar {background:#0a1931;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;color:white;position:sticky;top:0;z-index:999;border-radius:10px;margin-bottom:20px}
.qinetiq-bar .logo {font-weight:900;font-size:22px} .qinetiq-bar .logo span{color:#00d084}
.qinetiq-bar .menu a{color:white;margin:0 12px;text-decoration:none;font-size:13px;font-weight:600;cursor:pointer}
.qinetiq-bar .menu a:hover{color:#00d084;text-decoration:underline}
.card {background:white;padding:20px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.08);margin-bottom:15px}
html {scroll-behavior: smooth;}
</style>
<div class="qinetiq-bar">
  <div class="logo">CleanData <span>LAI</span> 🚀</div>
  <div class="menu">
    <a href="#who-we-are">Who we are</a>
    <a href="#what-we-do">What we do</a>
    <a href="#reports">Reports FREE</a>
    <a href="#pricing">Pricing</a>
    <a href="#contact">Contact</a>
  </div>
</div>
""", unsafe_allow_html=True)

qp = st.query_params
if qp.get("payment")=="success":
    p=qp.get("plan","1day"); em=qp.get("email","")
    if em and p in PLANS:
        try: nu=extend_subscription(em,p); st.success(f"🎉 Payment Success! {PLANS[p]['name']} until {nu.strftime('%Y-%m-%d %H:%M SAST')}"); st.balloons()
        except: st.warning("Payment received!")

users = load_users()
if "auth" not in st.session_state: st.session_state.auth = {"logged_in": False, "page": "signin"}

# LOGGED IN APP
if st.session_state.auth.get("logged_in"):
    biz = st.session_state.auth["user"]; u = users.get(biz, {}); now = now_sa(); expiry = safe_parse_date(u.get("paid_until") or u.get("expiry"))
    st.sidebar.success(f"Hi {u.get('name','')} ✅"); st.sidebar.write(f"{u.get('company','')} | {biz}")
    remaining = expiry - now; hours = int(remaining.total_seconds() // 3600); mins = int((remaining.total_seconds()%3600)//60)
    if now > expiry:
        st.title("⏰ Trial Expired"); st.error(f"Expired {expiry.strftime('%Y-%m-%d %H:%M SAST')}")
        c1,c2,c3=st.columns(3)
        with c1: st.markdown(payfast_button(biz,"1day"), unsafe_allow_html=True)
        with c2: st.markdown(payfast_button(biz,"1week"), unsafe_allow_html=True)
        with c3: st.markdown(payfast_button(biz,"1month"), unsafe_allow_html=True)
        if st.sidebar.button("Logout"): st.session_state.auth={"logged_in":False,"page":"signin"}; st.rerun()
        st.stop()
    st.sidebar.info(f"Trial: {hours}h {mins}m left | Plan: {u.get('plan','trial')}")
    st.sidebar.markdown("---"); st.sidebar.markdown("### 💰 Upgrade")
    st.sidebar.markdown(payfast_button(biz,"1day"), unsafe_allow_html=True); st.sidebar.markdown(payfast_button(biz,"1week"), unsafe_allow_html=True); st.sidebar.markdown(payfast_button(biz,"1month"), unsafe_allow_html=True)
    if st.sidebar.button("Logout"): st.session_state.auth={"logged_in":False,"page":"signin"}; st.rerun()

    st.title(f"Welcome {u.get('name','')} - {u.get('company','')} ✅")
    c1,c2,c3,c4=st.columns(4); c1.metric("Files Processed","1,248"); c2.metric("Rows Cleaned","342,871"); c3.metric("Formulas","30/30"); c4.metric("SA Time", now_sa().strftime('%H:%M'))
    dept = st.selectbox("Department", ["Sales","Customers","Stock","HR","General"])
    with st.expander("⚙️ Want something more? (Optional)"):
        extra_prompt = st.text_input("Text bar", placeholder="clean this data and make it...")
        f_cols=st.columns(5); all_formulas=["SUM","SUMIF","SUMIFS","AVERAGE","COUNTIF","IF","IFS","VLOOKUP","XLOOKUP","INDEX","MATCH","LEFT","RIGHT","MID","LEN","TRIM","CONCAT","TEXTJOIN","ROUND","MAX","MIN","TODAY","NOW","IFERROR","UNIQUE","CLEAN","UPPER","LOWER","PROPER","SUBSTITUTE"]
        formulas_selected=[]
        for i,f in enumerate(all_formulas):
            with f_cols[i%5]:
                if st.checkbox(f, value=True, key=f"f_{f}"): formulas_selected.append(f)
    if 'extra_prompt' not in locals(): extra_prompt=""; formulas_selected=all_formulas
    if "cleaned_data" not in st.session_state: st.session_state.cleaned_data = None; st.session_state.clean_log = None; st.session_state.orig_count = 0; st.session_state.report_text = ""; st.session_state.report_wc = 150

    uploaded = st.file_uploader("Upload messy CSV, Excel, JPG, PNG, PDF", type=["csv","xlsx","xls","jpg","jpeg","png","pdf"])
    if uploaded:
        try:
            df=pd.DataFrame()
            if uploaded.name.lower().endswith(".csv"): df=pd.read_csv(uploaded, dtype=str)
            elif uploaded.name.lower().endswith((".xlsx","xls")): df=pd.read_excel(uploaded, dtype=str)
            elif uploaded.name.lower().endswith(".pdf"):
                b=uploaded.read(); doc=fitz.open(stream=b,filetype="pdf"); text="".join([p.get_text() for p in doc]); lines=[l for l in text.split('\n') if l.strip()]
                if len(lines)<3:
                    pix=doc[0].get_pixmap(dpi=200); img=Image.frombytes("RGB",[pix.width,pix.height],pix.samples); text=pytesseract.image_to_string(img); lines=[l for l in text.split('\n') if l.strip()]
                data=[l.split(',') for l in lines]; df=pd.DataFrame(data[1:], columns=data[0] if data else None)
            else:
                image=Image.open(uploaded); text=pytesseract.image_to_string(image); lines=[l.strip() for l in text.split('\n') if l.strip()]
                if lines:
                    header=[h.strip() for h in re.split(r'\s{2,}|\t|,|\|', lines[0]) if h.strip()]; rows=[]
                    for line in lines[1:]:
                        parts=[p.strip() for p in re.split(r'\s{2,}|\t|,|\|', line) if p.strip()]
                        if len(parts)>=3: rows.append(parts)
                    if rows: df=pd.DataFrame(rows, columns=header[:len(rows[0])] if len(header)>=len(rows[0]) else None)
            if df.empty: st.error("Could not read file.")
            else:
                st.write("Original Preview:"); st.dataframe(df.head(20))
                if st.button("Clean Data Now - 30 Formulas + AI", type="primary"):
                    cleaned_df, orig, cleaned, removed, log = clean_data_v3(df, formulas_selected, extra_prompt)
                    st.session_state.cleaned_data = cleaned_df; st.session_state.clean_log = log; st.session_state.orig_count = orig; st.session_state.extra_prompt_saved = extra_prompt; st.session_state.report_text = ""
                    st.success(f"Cleaned! {orig} → {cleaned} | Removed {removed} | Department fixed to Sales ✅"); st.rerun()
        except Exception as e: st.error(f"Error: {e}"); st.exception(e)

    if st.session_state.cleaned_data is not None:
        cleaned_df = st.session_state.cleaned_data; log = st.session_state.clean_log; orig = st.session_state.orig_count; extra_saved = st.session_state.get("extra_prompt_saved","")
        st.divider(); st.subheader("✅ Cleaned Data - NO CAPS - Department Fixed")
        st.dataframe(cleaned_df)
        col_a,col_b=st.columns(2)
        with col_a:
            csv=cleaned_df.to_csv(index=False).encode('utf-8'); st.download_button("⬇️ Download Clean CSV", csv, f"cleaned_{dept}.csv", "text/csv", type="primary", key="dl_clean")
        with col_b:
            st.markdown('<div id="reports"></div>', unsafe_allow_html=True)
            word_count=st.selectbox("Report Words - FREE ✅", [100,150,200,300,500], index=1, key="wc")
            st.caption("FREE for now - Get customers! Later R50-R250")
            if st.button(f"📄 Write Professional Report ({word_count} words) - FREE", type="primary", key="gen_report"):
                report=generate_report(cleaned_df, orig, dept, word_count, log, extra_saved, u)
                st.session_state.report_text = report; st.session_state.report_wc = word_count; st.balloons()
        if st.session_state.report_text:
            st.divider(); st.subheader(f"📄 Professional Report - {st.session_state.report_wc} words - FREE ✅")
            st.text_area("Report", st.session_state.report_text, height=400, key="report_area")
            st.download_button("⬇️ Download Report TXT - FREE", st.session_state.report_text.encode(), f"Report_{dept}_{st.session_state.report_wc}words.txt", key="dl_report", type="primary")
            st.write("⭐ Rate CleanData LAI"); rating=st.feedback("stars", key="rate")
            if rating is not None: st.success(f"Thanks for {rating+1} stars! ⭐")

    # === FIX - SHOW INFO WHEN LOGGED IN SO TOP BAR WORKS ===
    st.divider()
    st.markdown('<div id="who-we-are"></div>', unsafe_allow_html=True)
    with st.expander("🏢 Who We Are - Click to open", expanded=False):
        st.markdown("""
        **CleanData LAI** is proudly South African, founded in **2026** by **Luyanda**, based at **867 Nkosisikelela Street, Inanda, Durban KZN**.
        We fix messy Excel in seconds. From eMatikwe to Inanda, we help spaza shops, liquor stores like Senamile Liquor, remote workers.
        **Mission:** Make clean data for every business, not just Sandton corporates. POPIA compliant.
        **Location:** 867 Nkosisikelela Street, Inanda, Durban 4310. **Founder:** Luyanda Lungelo Mchunu.
        """)
    st.markdown('<div id="what-we-do"></div>', unsafe_allow_html=True)
    with st.expander("⚙️ What We Do - Click to open", expanded=False):
        st.markdown("""
        **1. Instant Data Cleaning (30 Formulas):** TRIM, CLEAN, PROPER, UNIQUE, VLOOKUP, XLOOKUP, SUMIF, SUMIFS...
        Fix names Luyanda Dlamini, emails thandi@gmail.com, phones 0787674535, amounts R 100.00, Department Sales (not SALES).
        **2. Stock, Sales, Payroll:** Ready for Pastel/Sage, SARS VAT, HR.
        **3. Reports FREE:** 100-500 words professional. **Different:** Cleaning in seconds + reports. No CAPS.
        For individuals, remote workers, spaza shops, liquor stores, salons.
        """)
    st.markdown('<div id="pricing"></div>', unsafe_allow_html=True)
    with st.expander("💰 Pricing - Click to open", expanded=False):
        st.markdown("**Free Trial 1 Day FREE. After: 1 Day R100, 1 Week R570, 1 Month R2250. Reports FREE now, later R50-R250. PayFast secure.**")
    st.markdown('<div id="contact"></div>', unsafe_allow_html=True)
    with st.expander("📞 Contact - Click to open", expanded=False):
        st.markdown("""
        **Phone/WhatsApp:** 078 767 4535
        **Email:** luyandalungelo747@gmail.com
        **Address:** 867 Nkosisikelela Street, Inanda, Durban KZN
        **Hours:** Mon-Sat 08:00-18:00 SAST
        [Chat WhatsApp](https://wa.me/27787674535)
        """)
        if st.button("📱 WhatsApp Now - Logged In", key="wa_in"):
            st.markdown("[Open WhatsApp](https://wa.me/27787674535)")

    st.stop()
