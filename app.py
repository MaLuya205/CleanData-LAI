from pathlib import Path
import re, zipfile, py_compile, textwrap, os

src = Path("/mnt/data/cleandata_lai_upgrade/app.py").read_text(encoding="utf-8")

# Keep the upgraded premium login, 30 real cleaning/review operations, evidence-based reports,
# and exports, while making this an update to the user's existing CleanData LAI app.
src = src.replace(
'''def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(calculated.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
''',
'''def verify_password(password: str, stored: str) -> bool:
    """Verify new PBKDF2 hashes and legacy SHA-256 hashes from the old app."""
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
            if scheme != "pbkdf2_sha256":
                return False
            calculated = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(calculated.hex(), digest_hex)
        except (ValueError, TypeError):
            return False

    # Compatibility with the previous app's hashlib.sha256 password field.
    legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_digest, stored)
''')

# Upgrade legacy user records after a successful login; preserve the existing users.json data.
src = src.replace(
'''                record = users.get(email)
                if record and verify_password(password, record.get("password_hash", "")):
                    st.session_state.user_email = email
                    st.rerun()
''',
'''                record = users.get(email)
                stored_hash = ""
                if record:
                    stored_hash = record.get("password_hash") or record.get("password", "")
                if record and verify_password(password, stored_hash):
                    # Automatically upgrade old SHA-256 records to salted PBKDF2.
                    if not record.get("password_hash", "").startswith("pbkdf2_sha256$"):
                        record["password_hash"] = hash_password(password)
                        record.pop("password", None)
                        save_users(users)
                    st.session_state.user_email = email
                    st.rerun()
''')

# Set a one-day trial for new accounts; keep all original account fields compatible.
src = src.replace(
'''                    users[email] = {
                        "name": name.strip(),
                        "company": company.strip(),
                        "password_hash": hash_password(password),
                        "created_at": now_sa().isoformat(),
                    }
''',
'''                    users[email] = {
                        "name": name.strip(),
                        "company": company.strip(),
                        "password_hash": hash_password(password),
                        "created_at": now_sa().isoformat(),
                        "trial_expires_at": (now_sa() + timedelta(days=1)).isoformat(),
                        "plan": "1-day free trial",
                    }
''')

# Add a real public landing area that retains the existing product story and published pricing,
# but removes the precise street address from the public page for privacy.
public_site = r'''
def public_site():
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Built in South Africa · Clean data. Clear decisions.</div>
          <h1>Make messy spreadsheets<br>ready for real work.</h1>
          <p>Clean customer, sales, stock and operational data. Review every change, export your file and create a professional report based on actual results.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    about, services, pricing, contact = st.tabs(
        ["Who we are", "What we do", "Pricing", "Contact"]
    )
    with about:
        st.markdown(
            """
            ### Who We Are
            **CleanData LAI** is a South African data-cleaning project founded by Luyanda.
            It is designed to help individuals, remote workers and small businesses spend less
            time fixing messy spreadsheets and more time using their information.

            **Our focus:** practical cleaning, transparent processing logs, downloadable results
            and reports that describe what the uploaded data actually shows.
            """
        )
    with services:
        st.markdown(
            """
            ### What We Do
            - Clean text, names, headers and spacing.
            - Standardise email text and South African phone-number formats.
            - Convert date-like and numeric-looking columns where possible.
            - Detect exact duplicates and completely blank rows or columns.
            - Flag missing values, invalid email formats, possible outliers and negative amounts.
            - Export cleaned Excel and CSV files.
            - Generate a professional report with measured before-and-after figures.

            **Important:** these are 30 data-cleaning and review operations, not 30 Excel
            formulas. The app does not claim that XLOOKUP, SUMIFS or other spreadsheet
            formulas have run unless a matching calculation is specifically implemented.
            """
        )
    with pricing:
        st.markdown("### Pricing")
        p1, p2, p3 = st.columns(3)
        p1.markdown("**1 Day Pass**")
        p1.subheader("R100")
        p1.caption("For occasional one-off work")
        p2.markdown("**1 Week Pass**")
        p2.subheader("R570")
        p2.caption("For weekly stock or sales work")
        p3.markdown("**1 Month Pro**")
        p3.subheader("R2,250")
        p3.caption("For frequent business use")
        st.info(
            "These are the prices currently listed in your original app. "
            "Online payment activation is not enabled in this upgraded build. "
            "A verified PayFast server notification must be implemented before accepting payments."
        )
    with contact:
        st.markdown(
            """
            ### Contact
            **CleanData LAI · South Africa**

            Email: luyandalungelo747@gmail.com

            WhatsApp: [078 767 4535](https://wa.me/27787674535)

            For privacy, add a verified business mailing address here only if you want it
            publicly displayed and have confirmed it is suitable for publication.
            """
        )
    st.caption(
        "CleanData LAI provides data preparation and quality-review tools. "
        "It does not certify SARS, tax, payroll, accounting or POPIA compliance."
    )


'''
src = src.replace("\ndef main():\n", "\n" + public_site + "def main():\n")

# Render public information before authentication and dashboard.
src = src.replace(
'''def main():
    if "user_email" not in st.session_state:
        auth_page()
    else:
        main_app(st.session_state.user_email)
''',
'''def main():
    public_site()
    st.divider()
    if "user_email" not in st.session_state:
        auth_page()
    else:
        main_app(st.session_state.user_email)
''')

# Add trial status to the logged-in workspace without inventing usage statistics.
src = src.replace(
'''    account = users.get(email, {})
    st.markdown(
''',
'''    account = users.get(email, {})
    trial_text = account.get("trial_expires_at") or account.get("paid_until") or account.get("expiry")
    if trial_text:
        try:
            expiry = datetime.fromisoformat(str(trial_text))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=SA_TZ)
            current = now_sa()
            if current > expiry:
                st.warning(
                    "Your trial or recorded access period has expired. "
                    "Subscription payments are not enabled in this build yet; "
                    "do not send money until verified payment activation is available."
                )
                st.stop()
            st.caption(f"Access period ends: {expiry.strftime('%d %b %Y, %H:%M SAST')}")
        except (ValueError, TypeError):
            st.warning("We could not read the account expiry date. Please contact support.")
    st.markdown(
''')

# Keep the README accurate for this integrated replacement.
outdir = Path("/mnt/data/CleanData_LAI_GitHub_Replacement")
outdir.mkdir(exist_ok=True)
app_path = outdir / "app.py"
app_path.write_text(src, encoding="utf-8")

req = """streamlit>=1.36
pandas>=2.1
openpyxl>=3.1
xlrd>=2.0.1
"""
(outdir / "requirements.txt").write_text(req, encoding="utf-8")

readme = """# CleanData LAI — replacement files for your existing GitHub repository

These files are intended to replace the matching files in your existing Streamlit project.

## Replace
1. Back up your current `app.py` and `users.json` first.
2. Replace the repository's `app.py` with this `app.py`.
3. Replace/update `requirements.txt` with the included requirements.
4. Commit and push to GitHub. Streamlit Community Cloud should redeploy automatically.

## Important compatibility notes
- Existing accounts stored in the old `users.json` with SHA-256 hashes are supported.
  On the first successful login, the password hash is upgraded to salted PBKDF2.
- Keep the existing `users.json` file if you need to retain local account records.
- Streamlit Community Cloud's local filesystem is not a reliable permanent database.
  Before public commercial launch, move accounts and customer data to a managed database.
- This build does not activate subscriptions from a browser return URL. PayFast must be
  integrated with a server-side ITN notification, signature verification, amount/status
  checks and duplicate-notification protection before taking real payments.
- The old app's public street address has intentionally not been copied into the new
  public page. Add a verified business address only if you want it publicly displayed.
- The 30 items are actual cleaning/review operations, not 30 Excel formulas.
- PDF/image OCR was not carried forward because the old extraction path could produce
  unreliable columns. This version accepts CSV and Excel files.
"""
(outdir / "README.md").write_text(readme, encoding="utf-8")

# Syntax validation
py_compile.compile(str(app_path), doraise=True)

zip_path = Path("/mnt/data/CleanData_LAI_GitHub_Replacement.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for f in outdir.iterdir():
        z.write(f, arcname=f.name)

print("Created and syntax-checked:")
print(app_path, app_path.stat().st_size, "bytes")
print(outdir / "requirements.txt")
print(zip_path, zip_path.stat().st_size, "bytes")
