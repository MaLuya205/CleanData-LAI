import streamlit as st
import pandas as pd
import re
import fitz
import pytesseract
from PIL import Image
from datetime import datetime, timedelta
import json, os, hashlib, random

st.set_page_config(page_title="CleanData LAI - KZN", layout="wide")

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
except:
    USE_FIREBASE = False

def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

PLANS = {
    "1day": {"name": "1 Day Pass", "price": "100.00", "days": 1},
    "1week": {"name": "1 Week Pass", "price": "570.00", "days": 7},
    "1month": {"name": "1 Month Pro", "price": "2250.00", "days": 30}
}

def load_users_local():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE,"r") as f: return json.load(f)
        except: return {}
    return {}
def save_users_local(u):
    with open(USERS_FILE,"w") as f: json.dump(u,f)

# ---------- EMAIL VERIFICATION - RETURNED! ----------
def generate_code():
    return str(random.randint(100000, 999999))

def signup(email,password):
    email=email.lower().strip(); pwd=hash_pwd(password)
    code=generate_code()
    if USE_FIREBASE:
        doc=db.collection("users").document(email)
        if doc.get().exists: return False,"❌ User already exists! Please Login.", None
        doc.set({
            "password":pwd,
            "created_at":datetime.now().isoformat(),
            "paid_until":(datetime.now()+timedelta(hours=24)).isoformat(),
            "plan":"trial",
            "verified":False,  # NOT VERIFIED YET!
            "verify_code":code,
            "verify_expires":(datetime.now()+timedelta(minutes=15)).isoformat()
        })
        return True,f"✅ Account created! Verification code sent to {email}", code
    users=load_users_local()
    if email in users: return False,"❌ User already exists! Please Login.", None
    users[email]={
        "password":pwd,
        "created_at":datetime.now().isoformat(),
        "paid_until":(datetime.now()+timedelta(hours=24)).isoformat(),
        "plan":"trial",
        "verified":False,
        "verify_code":code,
        "verify_expires":(datetime.now()+timedelta(minutes=15)).isoformat()
    }
    save_users_local(users)
    return True,f"✅ Account created! Verification code sent to {email}", code

def verify_email_func(email,code):
    email=email.lower().strip()
    if USE_FIREBASE:
        doc=db.collection("users").document(email)
        d=doc.get()
        if not d.exists: return False,"❌ Email not found."
        data=d.to_dict()
        if data.get("verified"): return True,"✅ Already verified! You can login."
        if data.get("verify_code")!=code: return False,"❌ Wrong code. Try again."
        exp=datetime.fromisoformat(data.get("verify_expires"))
        if datetime.now()>exp: return False,"❌ Code expired. Sign up again."
        doc.update({"verified":True})
        return True,"✅ Email verified! Now you can login!"
    users=load_users_local()
    if email not in users: return False,"❌ Email not found."
    if users[email].get("verified"): return True,"✅ Already verified!"
    if users[email].get("verify_code")!=code: return False,"❌ Wrong code."
    exp=datetime.fromisoformat(users[email].get("verify_expires"))
    if datetime.now()>exp: return False,"❌ Code expired. Sign up again."
    users[email]["verified"]=True
    save_users_local(users)
    return True,"✅ Email verified! Now login!"

def login(email,password):
    email=email.lower().strip(); pwd=hash_pwd(password)
    if USE_FIREBASE:
        doc=db.collection("users").document(email).get()
        if not doc.exists: return False,"❌ Email not found. Sign up first."
        data=doc.to_dict()
        if not data.get("verified"): return False,"❌ Email not verified! Please verify your email first. Check your inbox or Verify tab."
        if data["password"]!=pwd: return False,"❌ Wrong password."
        exp=datetime.fromisoformat(data.get("paid_until"))
        if datetime.now()>exp: return False,f"❌ {data.get('plan')} expired {exp.strftime('%Y-%m-%d')}. Renew!"
        return True,f"✅ Login ok - {data.get('plan')}"
    users=load_users_local()
    if email not in users: return False,"❌ Email not found."
    if not users[email].get("verified"): return False,"❌ Email not verified! Go to Verify Email tab and enter code."
    if users[email]["password"]!=pwd: return False,"❌ Wrong password."
    exp=datetime.fromisoformat(users[email].get("paid_until"))
    if datetime.now()>exp: return False,f"❌ Expired. Renew!"
    return True,"✅ Login ok"

def get_user_status(email):
    email=email.lower().strip()
    if USE_FIREBASE:
        doc=db.collection("users").document(email).get()
        if doc.exists:
            d=doc.to_dict(); exp=datetime.fromisoformat(d.get("paid_until"))
            return (datetime.now()<exp), exp, d.get("plan","trial")
        return False,None,"not_found"
    users=load_users_local()
    if email in users:
        exp=datetime.fromisoformat(users[email].get("paid_until"))
        return (datetime.now()<exp), exp, users[email].get("plan","trial")
    return False,None,"not_found"

def extend_subscription(email,plan_key):
    email=email.lower().strip(); days=PLANS[plan_key]["days"]; new_until=datetime.now()+timedelta(days=days)
    if USE_FIREBASE:
        db.collection("users").document(email).update({"paid_until":new_until.isoformat(),"plan":plan_key,"last_payment":datetime.now().isoformat()})
    else:
        users=load_users_local()
        if email in users:
            users[email]["paid_until"]=new_until.isoformat(); users[email]["plan"]=plan_key; save_users_local(users)
    return new_until

def get_payfast_creds():
    if "payfast" in st.secrets:
        return st.secrets["payfast"]["merchant_id"], st.secrets["payfast"]["merchant_key"], "https://www.payfast.co.za/eng/process"
    else:
        return "10000100","46f0cd694581a","https://sandbox.payfast.co.za/eng/process"

def payfast_button(email,plan_key):
    plan=PLANS[plan_key]; mid,mkey,url=get_payfast_creds()
    data={"merchant_id":mid,"merchant_key":mkey,"return_url":f"https://cleandatalai.co.za?payment=success&plan={plan_key}&email={email}","cancel_url":"https://cleandatalai.co.za?payment=cancelled","notify_url":"https://cleandatalai.co.za/api/notify","m_payment_id":f"{email}|{plan_key}|{datetime.now().timestamp()}","amount":plan["price"],"item_name":f"CleanData {plan['name']}","item_description":f"{plan['days']} days","email_address":email}
    html=f'<form action="{url}" method="post">'
    for k,v in data.items(): html+=f'<input type="hidden" name="{k}" value="{v}">'
    color="#ff6600" if plan_key=="1day" else "#0066ff" if plan_key=="1week" else "#00aa44"
    html+=f'<button type="submit" style="background:{color};color:white;padding:14px;border:none;border-radius:10px;font-weight:bold;width:100%;">🔒 Pay R{plan["price"]} - {plan["name"]}</button></form>'
    return html

def clean_data(df):
    orig=len(df); df=df.dropna(how='all')
    df=df[~df.astype(str).apply(lambda x: x.str.contains('#ERROR|N/A',na=False)).any(axis=1)]
    df.columns=[str(c).strip() for c in df.columns]
    mp={}
    for c in df.columns:
        lc=c.lower()
        if "name" in lc: mp[c]="Full Name"
        elif "phone" in lc or "cell" in lc: mp[c]="Phone Number"
        elif "email" in lc: mp[c]="Email"
        elif "amount" in lc or "rand" in lc or "price" in lc: mp[c]="Amount (R)"
        elif "sale" in lc: mp[c]="Sales"
    df=df.rename(columns=mp)
    if "Full Name" in df.columns: df["Full Name"]=df["Full Name"].astype(str).str.strip().str.title()
    if "Phone Number" in df.columns: df["Phone Number"]=df["Phone Number"].astype(str).str.replace(r'\D','',regex=True)
    if "Email" in df.columns: df["Email"]=df["Email"].astype(str).str.strip().str.lower()
    if "Amount (R)" in df.columns:
        df["Amount (R)"]=df["Amount (R)"].astype(str).str.replace(',','',regex=False).str.extract(r'(\d+\.?\d*)')[0]
        df["Amount (R)"]=df["Amount (R)"].apply(lambda x: f"R {float(x):.2f}" if pd.notna(x) and str(x)!='' else "")
    for col in df.columns:
        if col not in ["Full Name","Phone Number","Email","Amount (R)"]:
            df[col]=df[col].astype(str).str.strip().str.lower().str.title()
    return df,orig,len(df),orig-len(df)

# ---------- UI ----------
st.title("🧹 CleanData LAI - KZN")

qp=st.query_params
if qp.get("payment")=="success":
    p=qp.get("plan","1day"); em=qp.get("email","")
    if em and p in PLANS:
        try:
            new_until=extend_subscription(em,p); st.success(f"🎉 Payment Success! {PLANS[p]['name']} until {new_until.strftime('%Y-%m-%d')}"); st.balloons()
        except: st.warning("Payment received! Contact support.")

if "logged_in" not in st.session_state: st.session_state.logged_in=False; st.session_state.user_email=""

if not st.session_state.logged_in:
    tab1,tab2,tab3=st.tabs(["Login","Sign Up","Verify Email"])
    with tab1:
        e=st.text_input("Email",key="le"); pw=st.text_input("Password",type="password",key="lp")
        if st.button("Login"):
            ok,msg=login(e,pw)
            if ok: st.session_state.logged_in=True; st.session_state.user_email=e.lower(); st.success(msg); st.rerun()
            else: st.error(msg)
    with tab2:
        e2=st.text_input("Email",key="se"); pw2=st.text_input("Password",type="password",key="sp")
        if st.button("Create Account - Send Verification"):
            ok,msg,code=signup(e2,pw2)
            if ok:
                st.success(msg)
                # SHOW CODE FOR TESTING - IN REAL APP SEND VIA EMAIL
                st.info(f"🔐 TESTING MODE: Your verification code is: **{code}**")
                st.warning("In real website, this code will be sent to email via SendGrid. For now copy it and go to Verify Email tab!")
                # TODO: Add real email sending here with SendGrid
                # send_email(e2, f"Your CleanData code is {code}")
            else: st.error(msg)
    with tab3:
        st.markdown("### 📧 Verify Your Email")
        ev=st.text_input("Email to verify",key="ve"); cv=st.text_input("6-digit code",key="vc")
        if st.button("Verify Email Now"):
            ok,msg=verify_email_func(ev,cv)
            if ok: st.success(msg); st.info("Now go to Login tab!")
            else: st.error(msg)
    st.stop()

# Logged in etc...
st.sidebar.write(f"✅ {st.session_state.user_email}")
is_active,exp,plan=get_user_status(st.session_state.user_email)
if not is_active:
    st.sidebar.error(f"Expired {plan}")
    st.error("⏰ Renew to continue")
    c1,c2,c3=st.columns(3)
    with c1: st.markdown("#### R100 1 Day"); st.markdown(payfast_button(st.session_state.user_email,"1day"),unsafe_allow_html=True)
    with c2: st.markdown("#### R570 1 Week"); st.markdown(payfast_button(st.session_state.user_email,"1week"),unsafe_allow_html=True)
    with c3: st.markdown("#### R2250 1 Month"); st.markdown(payfast_button(st.session_state.user_email,"1month"),unsafe_allow_html=True)
    if st.sidebar.button("Logout"): st.session_state.logged_in=False; st.rerun()
    st.stop()
else:
    st.sidebar.success(f"Active {plan} until {exp.strftime('%Y-%m-%d')}")
    if st.sidebar.button("Logout"): st.session_state.logged_in=False; st.rerun()

uploaded=st.file_uploader("Upload CSV/Excel/Image/PDF",type=["csv","xlsx","xls","jpg","png","pdf"])
if uploaded:
    df=pd.DataFrame()
    if uploaded.name.lower().endswith(".csv"): df=pd.read_csv(uploaded,dtype=str)
    elif uploaded.name.lower().endswith((".xlsx","xls")): df=pd.read_excel(uploaded,dtype=str)
    elif uploaded.name.lower().endswith(".pdf"):
        doc=fitz.open(stream=uploaded.read(),filetype="pdf"); txt="".join([p.get_text() for p in doc]); lines=[l for l in txt.split('\n') if l.strip()]; data=[l.split(',') for l in lines]; df=pd.DataFrame(data[1:],columns=data[0]) if data else pd.DataFrame()
    else:
        img=Image.open(uploaded); txt=pytesseract.image_to_string(img); lines=[l.strip() for l in txt.split('\n') if l.strip()]
        if lines:
            hdr=[h.strip() for h in re.split(r'\s{2,}|\t|,',lines[0]) if h.strip()]
            rows=[[p.strip() for p in re.split(r'\s{2,}|\t|,',l) if p.strip()] for l in lines[1:]]
            df=pd.DataFrame(rows,columns=hdr[:len(rows[0])] if hdr else None)
    if df.empty: st.error("Can't read")
    else:
        st.dataframe(df.head(20))
        if st.button("Clean Now",type="primary"):
            cdf,o,c,r=clean_data(df); st.success(f"{o}->{c} Removed {r}"); st.dataframe(cdf)
            st.download_button("Download",cdf.to_csv(index=False).encode('utf-8'),"cleaned.csv","text/csv")
