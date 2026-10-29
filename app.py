if choice == "Sign Up":
    st.title("Create Your Business Account")
    
    name = st.text_input("Your Full Name *", placeholder="Luyanda Dlamini", key="su_name")
    company = st.text_input("Company / Business Name *", placeholder="eMatikwe General Store", key="su_comp")
    phone = st.text_input("Business Phone *", placeholder="078 767 4535", key="su_phone")
    email = st.text_input("Business Email *", placeholder="shop@gmail.com", key="su_email")
    
    st.markdown("### Create Password *")
    pwd = st.text_input("Create Password", type="password", placeholder="e.g. Shop@2026", key="su_pwd", label_visibility="collapsed")
    
    # --- LIVE CHECK WHILE TYPING ---
    if pwd:
        has_len = len(pwd) >= 8
        has_letter = sum(c.isalpha() for c in pwd) >= 1
        has_num = sum(c.isdigit() for c in pwd) >= 2
        has_sym = sum(not c.isalnum() for c in pwd) >= 1
        
        # Show checklist with ticks
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"{'✅' if has_len else '❌'} At least 8 characters ({len(pwd)}/8)")
            st.write(f"{'✅' if has_letter else '❌'} At least 1 letter")
        with col2:
            st.write(f"{'✅' if has_num else '❌'} At least 2 numbers ({sum(c.isdigit() for c in pwd)}/2)")
            st.write(f"{'✅' if has_sym else '❌'} At least 1 symbol (!@#$%)")
        
        # Strength bar
        score = sum([has_len, has_letter, has_num, has_sym])
        if score == 4:
            st.success("🔥 Strong password! Good to go ✅")
            strong = True
        elif score == 3:
            st.warning("Almost! Add 1 more thing")
            strong = False
        else:
            st.error(f"Weak - {score}/4 done")
            strong = False
    else:
        strong = False
        st.info("💡 Password must have: 8 chars, 1 letter, 2 numbers, 1 symbol like Shop@44")

    pwd2 = st.text_input("Confirm Password *", type="password", key="su_pwd2")
    
    if st.button("Create Account & Send Code", type="primary"):
        if not all([name, company, phone, email, pwd]):
            st.error("Fill all fields!")
        elif "@" not in email:
            st.error("Enter valid email")
        elif pwd != pwd2:
            st.error("Passwords don't match!")
        elif not strong:
            st.error("❌ Password not strong enough! Check the ticks above")
        elif email in users:
            st.error("Email already exists! Go to Sign In")
        else:
            code = str(random.randint(100000, 999999))
            st.session_state.pending = {"name":name, "company":company, "phone":phone, "email":email, "pwd":hash_pwd(pwd), "code":code, "time":datetime.now()}
            send_code(email, code, name)
            st.session_state.auth["page"] = "verify_signup"
            st.success(f"Code sent to {email}!")
            st.rerun()
