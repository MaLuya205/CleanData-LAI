import streamlit as st, pandas as pd, os, json, random, smtplib, hashlib, re
from datetime import datetime, timedelta
from email.mime.text import MIMEText

st.set_page_config(page_title="CleanData Pro - Login", layout="wide")
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try: return json.load(open(USERS_FILE))
        except: return {}
    return {}
def save_users(d):
    json.dump(d, open(USERS_FILE,"w"), indent=2)

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# --- NEW STRONG PASSWORD CHECK ---
def check_strong_password(pwd):
    if len(pwd) < 8:
        return False, "Too short! Use at least 8 characters (e.g. Shop@2026)"
    nums = sum(c.isdigit() for c in pwd)
    letters = sum(c.isalpha() for c in pwd)
    symbols = sum(not c.isalnum() for c in pwd)
    if letters < 1:
        return False, "Weak! Add at least 1 letter (A-Z)"
    if nums < 2:
        return False, f"Weak! You have {nums} number, need at least 2 numbers (e.g. ...44)"
    if symbols < 1:
        return False, "Weak! Add at least 1 symbol (! @ # $ % & *) e.g. Shop@44"
    return True, "Strong password ✅"

def send_code(to_email, code, name=""):
    try:
        user = st.secrets["EMAIL_USER"]
        pwd = st.secrets["EMAIL_PASS"]
        body = f"Hi {name},\n\nYour CleanData Pro verification code is: {code}\nValid for 10 minutes.\n\nMaLuya Team"
        msg = MIMEText(body)
        msg["Subject"] = f"CleanData Pro - Your code {code}"
        msg["From"] = user
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:
        st.warning(f"Test mode - Your code is: {code} (Email error: {e})")
        return True

users = load_users()
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "page": "signin"}

# LOGGED IN APP
if st.session_state.auth.get("logged_in"):
    biz = st.session_state.auth["user"]
    u = users.get(biz)
    now = datetime.now()
    expiry = datetime.fromisoformat(u["expiry"])
    st.sidebar.success(f"Hi {u['name']} ✅")
    st.sidebar.write(f"**{u['company']}** | {biz}")
    remaining = expiry - now
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600)//60)
    if now > expiry:
        st.title("⏰ Trial Expired")
        st.error(f"Expired {expiry}")
        st.link_button("💬 WhatsApp to Pay", f"https://wa.me/27787674535?text=Pay%20ID:{biz}")
        if st.sidebar.button("Logout"):
            st.session_state.auth = {"logged_in": False, "page": "signin"}
            st.rerun()
        st.stop()
    st.sidebar.info(f"Trial: {hours}h {mins}m left")
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "page": "signin"}
        st.rerun()
    st.title(f"Welcome {u['name']} - {u['company']} ✅")
    dept = st.selectbox("Department", ["Sales","Customers","Stock","HR","General"])
    uploaded = st.file_uploader("Upload file", type=["csv","xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.dataframe(df.head())
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df = df.drop_duplicates().replace(["#DIV/0!","#N/A","#REF!","#VALUE!","nan","None","NaN",""],"").fillna("")
        st.success(f"✅ Cleaned {len(df)} rows")
        st.download_button("⬇️ Download", df.to_csv(index=False).encode('utf-8'), f"cleaned_{dept}.csv")
    st.stop()

# SIGN IN / SIGN UP
st.sidebar.title("CleanData Pro")
choice = st.sidebar.radio("Choose", ["Sign In", "Sign Up"], index=0 if st.session_state.auth["page"]=="signin" else 1)

if choice == "Sign Up":
    st.title("Create Your Business Account")
    st.markdown("**Password must be strong to stop hackers!**")
    with st.form("signup"):
        name = st.text_input("Your Full Name *")
        company = st.text_input("Company / Business Name *")
        phone = st.text_input("Business Phone *", placeholder="078 767 4535")
        email = st.text_input("Business Email *")
        pwd = st.text_input("Create Password *", type="password", help="At least 8 chars, 2 numbers, 1 symbol like !@#$")
        pwd2 = st.text_input("Confirm Password *", type="password")
        # LIVE STRENGTH METER
        if pwd:
            ok, msg = check_strong_password(pwd)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        submitted = st.form_submit_button("Create Account & Send Code")
    
    if submitted:
        ok, msg = check_strong_password(pwd)
        if not all([name, company, phone, email, pwd]):
            st.error("Fill all fields!")
        elif "@" not in email:
            st.error("Enter valid email")
        elif pwd != pwd2:
            st.error("Passwords don't match!")
        elif not ok:
            st.error(f"❌ {msg}")
        elif email in users:
            st.error("Email already exists! Go to Sign In")
        else:
            code = str(random.randint(100000, 999999))
            st.session_state.pending = {"name":name, "company":company, "phone":phone, "email":email, "pwd":hash_pwd(pwd), "code":code, "time":datetime.now()}
            send_code(email, code, name)
            st.session_state.auth["page"] = "verify_signup"
            st.success(f"Code sent to {email}!")
            st.rerun()

    if st.session_state.auth["page"] == "verify_signup" and "pending" in st.session_state:
        st.divider()
        st.subheader(f"Verify {st.session_state.pending['email']}")
        c = st.text_input("Enter 6-digit code")
        if st.button("Verify & Start Trial"):
            p = st.session_state.pending
            if c != p["code"]:
                st.error("Wrong code!")
            elif datetime.now() - p["time"] > timedelta(minutes=10):
                st.error("Code expired - Create account again")
            else:
                now = datetime.now()
                users[p["email"]] = {"name": p["name"], "company": p["company"], "phone": p["phone"], "password": p["pwd"], "verified": True, "created": now.isoformat(), "start": now.isoformat(), "expiry": (now + timedelta(days=1)).isoformat()}
                save_users(users)
                st.session_state.auth = {"logged_in": True, "user": p["email"], "page": "signin"}
                del st.session_state.pending
                st.success("Account created! Trial started!")
                st.rerun()

else:
    st.title("Welcome Back - Sign In")
    with st.form("signin"):
        email = st.text_input("Business Email")
        pwd = st.text_input("Password", type="password")
        login = st.form_submit_button("Sign In")
    if login:
        if email not in users:
            st.error("No account with this email! Go to Sign Up")
        elif users[email]["password"] != hash_pwd(pwd):
            st.error("Wrong password!")
        else:
            st.session_state.auth = {"logged_in": True, "user": email, "page": "signin"}
            st.rerun()
