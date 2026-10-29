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

def check_strong_password(pwd):
    if len(pwd) < 8:
        return False, "Too short! Use at least 8 chars"
    nums = sum(c.isdigit() for c in pwd)
    letters = sum(c.isalpha() for c in pwd)
    symbols = sum(not c.isalnum() for c in pwd)
    if letters < 1:
        return False, "Add at least 1 letter"
    if nums < 2:
        return False, f"Need 2 numbers, you have {nums}"
    if symbols < 1:
        return False, "Add 1 symbol (!@#$%)"
    return True, "Strong ✅"

def send_code(to_email, code, name=""):
    try:
        user = st.secrets["EMAIL_USER"]
        pwd = st.secrets["EMAIL_PASS"]
        body = f"Hi {name},\n\nYour CleanData Pro code is: {code}\nValid 10 min.\n\nMaLuya Team"
        msg = MIMEText(body)
        msg["Subject"] = f"CleanData Pro - Your code {code}"
        msg["From"] = user
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:
        st.warning(f"Test mode - Your code is: {code}")
        return True

users = load_users()
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "page": "signin"}

# LOGGED IN
if st.session_state.auth.get("logged_in"):
    biz = st.session_state.auth["user"]
    u = users.get(biz, {})
    now = datetime.now()
    expiry = datetime.fromisoformat(u.get("expiry", now.isoformat()))
    st.sidebar.success(f"Hi {u.get('name','')} ✅")
    st.sidebar.write(f"{u.get('company','')} | {biz}")
    remaining = expiry - now
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600)//60)
    if now > expiry:
        st.title("⏰ Trial Expired")
        st.error(f"Expired {expiry}")
        st.link_button("💬 WhatsApp to Pay 078 767 4535", f"https://wa.me/27787674535?text=Pay%20ID:{biz}")
        if st.sidebar.button("Logout"):
            st.session_state.auth = {"logged_in": False, "page": "signin"}
            st.rerun()
        st.stop()
    st.sidebar.info(f"Trial: {hours}h {mins}m left")
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "page": "signin"}
        st.rerun()
    st.title(f"Welcome {u.get('name','')} - {u.get('company','')} ✅")
    dept = st.selectbox("Department", ["Sales","Customers","Stock","HR","General"])
    uploaded = st.file_uploader("Upload file", type=["csv","xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.dataframe(df.head())
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df = df.drop_duplicates().replace(["#DIV/0!","#N/A","#REF!","#VALUE!","nan","None","NaN",""],"").fillna("")
        st.success(f"✅ Cleaned {len(df)} rows")
        st.download_button("⬇️ Download Clean", df.to_csv(index=False).encode('utf-8'), f"cleaned_{dept}.csv")
    st.stop()

# NOT LOGGED IN
st.sidebar.title("CleanData Pro")
choice = st.sidebar.radio("Choose", ["Sign In", "Sign Up"], index=0 if st.session_state.auth["page"]=="signin" else 1)

if choice == "Sign Up":
    st.title("Create Your Business Account")
    st.markdown("Get 1-Day FREE Trial after email verification")
    name = st.text_input("Your Full Name *", placeholder="Luyanda Dlamini", key="su_name")
    company = st.text_input("Company / Business Name *", placeholder="eMatikwe Store", key="su_comp")
    phone = st.text_input("Business Phone *", placeholder="078 767 4535", key="su_phone")
    email = st.text_input("Business Email *", placeholder="shop@gmail.com", key="su_email")
    
    st.markdown("### Create Password *")
    pwd = st.text_input("Create Password", type="password", placeholder="e.g. Shop@2026", key="su_pwd", label_visibility="collapsed")
    
    strong = False
    if pwd:
        has_len = len(pwd) >= 8
        has_letter = sum(c.isalpha() for c in pwd) >= 1
        has_num = sum(c.isdigit() for c in pwd) >= 2
        has_sym = sum(not c.isalnum() for c in pwd) >= 1
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"{'✅' if has_len else '❌'} At least 8 chars ({len(pwd)}/8)")
            st.write(f"{'✅' if has_letter else '❌'} At least 1 letter")
        with col2:
            st.write(f"{'✅' if has_num else '❌'} At least 2 numbers ({sum(c.isdigit() for c in pwd)}/2)")
            st.write(f"{'✅' if has_sym else '❌'} At least 1 symbol (!@#$%)")
        
        score = sum([has_len, has_letter, has_num, has_sym])
        if score == 4:
            st.success("🔥 Strong password! Good to go ✅")
            strong = True
        elif score == 3:
            st.warning("Almost! Add 1 more thing")
        else:
            st.error(f"Weak - {score}/4 done")
    else:
        st.info("💡 Password must: 8 chars, 1 letter, 2 numbers, 1 symbol like Shop@44")

    pwd2 = st.text_input("Confirm Password *", type="password", key="su_pwd2")
    
    if st.button("Create Account & Send Code", type="primary"):
        if not all([name, company, phone, email, pwd]):
            st.error("Fill all fields!")
        elif "@" not in email:
            st.error("Enter valid email")
        elif pwd != pwd2:
            st.error("Passwords don't match!")
        elif not strong:
            st.error("❌ Password not strong enough! Check ticks above")
        elif email in users:
            st.error("Email already exists! Go to Sign In")
        else:
            code = str(random.randint(100000, 999999))
            st.session_state.pending = {"name":name, "company":company, "phone":phone, "email":email, "pwd":hash_pwd(pwd), "code":code, "time":datetime.now()}
            send_code(email, code, name)
            st.session_state.auth["page"] = "verify_signup"
            st.success(f"Code sent to {email}! Check Inbox/Spam")
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
                st.error("Code expired - Create again")
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
    with st.form("signin_form"):
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
