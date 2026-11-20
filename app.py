# ============================================================
# CleanData LAI - FULL FIXED CODE - PRO LEVEL
# Copy & Paste - All Logins Inside
# Fixes: Date DDMMYYYY | Colours | Invoice PRO | PDF Editable
# ============================================================
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import base64

# --- PDF - ReportLab ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ============================================================
# 1. CONFIG & DATE FIX - DDMMYYYY
# ============================================================
st.set_page_config(page_title="CleanData LAI", page_icon="🧹", layout="wide")

def fmt_date(d):
    """DDMMYYYY - 20/11/2026 - ALWAYS"""
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return d
    return d.strftime("%d/%m/%Y")

def fmt_date_noslash(d):
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return d
    return d.strftime("%d%m%Y")

TODAY = datetime.now().date()
TODAY_STR = fmt_date(TODAY)

# ============================================================
# 2. LOGINS - ALL LOGINS HERE
# ============================================================
USERS = {
    # Admin
    "admin": {"password": "admin123", "role": "admin", "name": "Admin - CleanData LAI"},
    # Companies
    "company1": {"password": "company123", "role": "company", "name": "ABC Cleaning (Pty) Ltd"},
    "sparkle": {"password": "sparkle123", "role": "company", "name": "Sparkle Clean Co"},
    # Individuals
    "thabo": {"password": "thabo123", "role": "individual", "name": "Thabo Mokoena"},
    "zanele": {"password": "zanele123", "role": "individual", "name": "Zanele Dube"},
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.name = None

# ============================================================
# 3. COLOURS - LOGIN SYSTEM COLOURS
# ============================================================
# LOGIN COLOURS = Deep Blue + White + Light Grey - NOT Black & Gold
LOGIN_BLUE = "#0B3D91"
LOGIN_BLUE_LIGHT = "#1565C0"
LOGIN_GREY = "#F2F4F7"
LOGIN_WHITE = "#FFFFFF"

def apply_theme(role):
    """Error #3 FIX: Companies = Login Colours, Individual = White + Black Text"""
    if role == "individual":
        # INDIVIDUAL: White background, BLACK text - so all words visible
        st.markdown(f"""
        <style>
        .stApp {{ background-color: #FFFFFF !important; color: #000000 !important; }}
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {{ color: #000000 !important; }}
        input, textarea, select {{ color: #000000 !important; background-color: #FFFFFF !important; border: 1px solid #CCCCCC !important; }}
        .stButton>button {{ background-color: {LOGIN_BLUE} !important; color: white !important; border: none; border-radius: 8px; }}
        </style>
        """, unsafe_allow_html=True)
    else:
        # COMPANY + ADMIN: Login System Colours - Blue / White / Grey
        st.markdown(f"""
        <style>
        .stApp {{ background-color: {LOGIN_GREY} !important; }}
        .main-header {{ background-color: {LOGIN_BLUE}; color: white; padding: 18px 22px; border-radius: 12px; }}
        .main-header h1, .main-header p {{ color: white !important; }}
        .stButton>button {{ background-color: {LOGIN_BLUE} !important; color: white !important; border: none; border-radius: 8px; }}
        .card {{ background: white; padding: 16px; border-radius: 12px; border: 1px solid #E0E0E0; }}
        label, p, span {{ color: #111111 !important; }}
        </style>
        """, unsafe_allow_html=True)

# ============================================================
# 4. LOGIN PAGE
# ============================================================
if not st.session_state.logged_in:
    st.markdown(f"""
    <div style="background:{LOGIN_BLUE}; padding:28px; border-radius:14px; text-align:center;">
        <h1 style="color:white; margin:0;">🧹 CleanData LAI</h1>
        <p style="color:white; margin:4px 0 0 0;">Cleaning Data • Invoices • Clients</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.subheader("Login")
        username = st.text_input("Username", placeholder="e.g. admin / company1 / thabo")
        password = st.text_input("Password", type="password")
        role_choice = st.selectbox("Login As", ["admin", "company", "individual"])
        if st.button("LOGIN", use_container_width=True):
            u = USERS.get(username.strip().lower())
            if u and u["password"] == password and u["role"] == role_choice:
                st.session_state.logged_in = True
                st.session_state.user = username.strip().lower()
                st.session_state.role = u["role"]
                st.session_state.name = u["name"]
                st.success(f"Welcome {u['name']}")
                st.rerun()
            else:
                st.error("Wrong username / password / role. Try admin / admin123")
        st.info("Demo Logins:\nAdmin: admin / admin123\nCompany: company1 / company123\nIndividual: thabo / thabo123")
    st.stop()

# Logged in - apply theme
apply_theme(st.session_state.role)

# ============================================================
# 5. HEADER + LOGOUT
# ============================================================
st.markdown(f"""
<div class="main-header">
    <h1 style="margin:0;">🧹 CleanData LAI</h1>
    <p style="margin:4px 0 0 0;">Welcome {st.session_state.name} • {st.session_state.role.upper()} • Date: {TODAY_STR} (DDMMYYYY)</p>
</div>
""", unsafe_allow_html=True)
st.write("")
if st.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ============================================================
# 6. DATA - In Session (Replace with your DB later)
# ============================================================
if "clients" not in st.session_state:
    st.session_state.clients = pd.DataFrame([
        {"Name": "ABC Cleaning", "Type": "Company", "Phone": "082 123 4567", "Email": "info@abc.co.za", "Date Added": TODAY_STR},
        {"Name": "Thabo Mokoena", "Type": "Individual", "Phone": "083 987 6543", "Email": "thabo@gmail.com", "Date Added": TODAY_STR},
    ])
if "invoices" not in st.session_state:
    st.session_state.invoices = []

# ============================================================
# 7. PRO INVOICE PDF - Error #4 FIX
# ============================================================
def generate_invoice_pdf(data):
    """PRO LEVEL INVOICE - Click to Edit fields BEFORE generation (Error #2)"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18*mm, bottomMargin=15*mm, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    BLUE = HexColor("#0B3D91")
    LIGHT_GREY = HexColor("#F2F4F7")
    DARK = HexColor("#111111")
    GREY_TEXT = HexColor("#555555")

    sTitle = ParagraphStyle("Title2", parent=styles["Normal"], fontSize=26, leading=28, textColor=BLUE, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    sSmall = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, leading=12, textColor=DARK, fontName="Helvetica")
    sSmallGrey = ParagraphStyle("SmallGrey", parent=styles["Normal"], fontSize=9, leading=12, textColor=GREY_TEXT, fontName="Helvetica")
    sSmallRight = ParagraphStyle("SmallRight", parent=styles["Normal"], fontSize=9, leading=12, textColor=DARK, fontName="Helvetica", alignment=TA_RIGHT)
    sCell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=9, leading=12, textColor=DARK, fontName="Helvetica")
    sCellRight = ParagraphStyle("CellRight", parent=styles["Normal"], fontSize=9, leading=12, textColor=DARK, fontName="Helvetica", alignment=TA_RIGHT)
    sCellHead = ParagraphStyle("CellHead", parent=styles["Normal"], fontSize=9, leading=12, textColor=white, fontName="Helvetica-Bold")
    sCellHeadRight = ParagraphStyle("CellHeadRight", parent=styles["Normal"], fontSize=9, leading=12, textColor=white, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    sTotal = ParagraphStyle("Total", parent=styles["Normal"], fontSize=13, leading=16, textColor=white, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    sTotalLabel = ParagraphStyle("TotalLabel", parent=styles["Normal"], fontSize=11, leading=14, textColor=white, fontName="Helvetica-Bold")

    story = []
    # HEADER BAR
    header_data = [
        [Paragraph(f"<b>{data['business_name']}</b><br/><font color='#555555'>{data['business_address']}<br/>Tel: {data['business_phone']} • {data['business_email']}<br/>VAT No: {data['vat_no']}</font>", sSmall),
         Paragraph("INVOICE", sTitle)]
    ]
    t = Table(header_data, colWidths=[95*mm, 75*mm])
    t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0)]))
    story.append(t)
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6, spaceBefore=6))

    # BILL TO + META - Date DDMMYYYY
    meta = [
        [Paragraph("<b>BILL TO</b>", sSmall), Paragraph(f"<b>Invoice No:</b> {data['invoice_no']}", sSmallRight)],
        [Paragraph(f"<b>{data['client_name']}</b><br/>{data['client_address']}<br/>Tel: {data['client_phone']}<br/>{data['client_email']}", sSmall),
         Paragraph(f"<b>Invoice Date:</b> {data['invoice_date']}<br/><b>Due Date:</b> {data['due_date']}<br/><b>VAT No:</b> {data['vat_no']}", sSmallRight)],
    ]
    t2 = Table(meta, colWidths=[85*mm, 85*mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), LIGHT_GREY),
        ("BOX", (0,0), (0,0), 0.5, HexColor("#DDDDDD")),
        ("BOX", (1,0), (1,-1), 0.5, HexColor("#DDDDDD")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 6*mm))

    # ITEMS TABLE - Full description, no cut-off
    items_header = [
        Paragraph("<b>#</b>", sCellHead),
        Paragraph("<b>DESCRIPTION</b>", sCellHead),
        Paragraph("<b>QTY</b>", sCellHeadRight),
        Paragraph("<b>UNIT PRICE (R)</b>", sCellHeadRight),
        Paragraph("<b>AMOUNT (R)</b>", sCellHeadRight),
    ]
    rows = [items_header]
    for i, it in enumerate(data["items"], start=1):
        rows.append([
            Paragraph(str(i), sCell),
            Paragraph(it["desc"], sCell),
            Paragraph(str(it["qty"]), sCellRight),
            Paragraph(f"{it['price']:,.2f}", sCellRight),
            Paragraph(f"{it['qty']*it['price']:,.2f}", sCellRight),
        ])
    colW = [10*mm, 75*mm, 20*mm, 32*mm, 33*mm]
    t3 = Table(rows, colWidths=colW, repeatRows=1)
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LIGHT_GREY]),
        ("GRID", (0,0), (-1,-1), 0.5, HexColor("#DDDDDD")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t3)
    story.append(Spacer(1, 4*mm))

    # TOTALS
    subtotal = sum(it["qty"]*it["price"] for it in data["items"])
    vat = subtotal * 0.15 if data["include_vat"] else 0
    total = subtotal + vat
    totals = [
        [Paragraph("Subtotal", sSmallRight), Paragraph(f"R {subtotal:,.2f}", sSmallRight)],
        [Paragraph("VAT (15%)", sSmallRight), Paragraph(f"R {vat:,.2f}", sSmallRight)],
    ]
    tt = Table(totals, colWidths=[120*mm, 50*mm])
    tt.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    story.append(tt)
    total_row = [[Paragraph("TOTAL DUE", sTotalLabel), Paragraph(f"R {total:,.2f}", sTotal)]]
    tTot = Table(total_row, colWidths=[120*mm, 50*mm])
    tTot.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), BLUE), ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8), ("ROUNDEDCORNERS", [4,4,4,4])]))
    story.append(tTot)
    story.append(Spacer(1, 5*mm))

    # BANKING + NOTES + TERMS - Full, no cut
    story.append(Paragraph("<b>BANKING DETAILS</b>", sSmall))
    story.append(Paragraph(f"{data['bank_name']} • Account: {data['account_no']} • Branch Code: {data['branch_code']} • Ref: {data['invoice_no']}", sSmall))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("<b>NOTES</b>", sSmall))
    story.append(Paragraph(data["notes"], sSmall))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("<b>PAYMENT TERMS</b>", sSmall))
    story.append(Paragraph("Please pay within 7 days of invoice date. Use Invoice Number as reference. Thank you for your business - CleanData LAI.", sSmallGrey))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#DDDDDD")))
    story.append(Paragraph(f"CleanData LAI • Page 1 • Generated {TODAY_STR}", ParagraphStyle("Foot", parent=styles["Normal"], fontSize=8, leading=10, textColor=GREY_TEXT, alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue(), total

# ============================================================
# 8. TABS - Dashboard / Clients / Invoice
# ============================================================
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "👥 Clients", "🧾 Invoice - PRO"])

with tab1:
    st.subheader(f"Dashboard - {TODAY_STR}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Clients", len(st.session_state.clients))
    m2.metric("Total Invoices", len(st.session_state.invoices))
    m3.metric("Today", TODAY_STR)
    st.write("### Recent Clients")
    st.dataframe(st.session_state.clients, use_container_width=True)

with tab2:
    st.subheader("Add Client")
    with st.form("add_client"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full Name / Company Name")
        phone = c2.text_input("Phone")
        email = c1.text_input("Email")
        typ = c2.selectbox("Type", ["Company", "Individual"])
        date_added = st.date_input("Date Added", value=TODAY)
        # Show DDMMYYYY preview
        st.caption(f"Date will show as: {fmt_date(date_added)} (DDMMYYYY)")
        if st.form_submit_button("Add Client"):
            if name:
                new = pd.DataFrame([{"Name": name, "Type": typ, "Phone": phone, "Email": email, "Date Added": fmt_date(date_added)}])
                st.session_state.clients = pd.concat([st.session_state.clients, new], ignore_index=True)
                st.success(f"Added {name} - Date: {fmt_date(date_added)}")
            else:
                st.error("Enter name first")
    st.write("### All Clients")
    st.dataframe(st.session_state.clients, use_container_width=True)

with tab3:
    st.subheader("🧾 PRO Invoice - Click To Edit (Error #2 Fix)")
    st.info("Edit ANY field below - then click Generate. The PDF will use your edited text. Like Acrobat, but before you generate.")
    # --- EDITABLE FIELDS ---
    colA, colB = st.columns(2)
    with colA:
        business_name = st.text_input("Your Business Name", value="CleanData LAI")
        business_address = st.text_area("Your Address", value="eMatikwe, KwaZulu-Natal, South Africa")
        business_phone = st.text_input("Your Phone", value="082 123 4567")
        business_email = st.text_input("Your Email", value="info@cleandata.co.za")
        vat_no = st.text_input("VAT No", value="4123456789")
    with colB:
        invoice_no = st.text_input("Invoice No", value=f"INV-{fmt_date_noslash(TODAY)}-001")
        invoice_date_obj = st.date_input("Invoice Date", value=TODAY)
        due_date_obj = st.date_input("Due Date", value=TODAY + timedelta(days=7))
        invoice_date = fmt_date(invoice_date_obj)
        due_date = fmt_date(due_date_obj)
        st.caption(f"Invoice Date: {invoice_date} | Due Date: {due_date} - DDMMYYYY")
        client_name = st.text_input("Bill To - Client Name", value="ABC Cleaning (Pty) Ltd")
        client_address = st.text_area("Client Address", value="Durban, KZN")
        client_phone = st.text_input("Client Phone", value="082 000 0000")
        client_email = st.text_input("Client Email", value="client@email.co.za")

    st.write("### Items")
    if "item_count" not in st.session_state:
        st.session_state.item_count = 2
    items = []
    for i in range(st.session_state.item_count):
        c1, c2, c3 = st.columns([4, 1, 2])
        d = c1.text_input(f"Description {i+1}", value="Deep Cleaning - Office" if i == 0 else "Window Cleaning", key=f"desc{i}")
        q = c2.number_input(f"Qty {i+1}", min_value=1, value=1, key=f"qty{i}")
        p = c3.number_input(f"Price R {i+1}", min_value=0.0, value=1500.0 if i == 0 else 800.0, key=f"price{i}")
        items.append({"desc": d, "qty": int(q), "price": float(p)})
    if st.button("+ Add Item"):
        st.session_state.item_count += 1
        st.rerun()

    st.write("### Banking & Notes")
    b1, b2, b3 = st.columns(3)
    bank_name = b1.text_input("Bank", value="Capitec Bank")
    account_no = b2.text_input("Account No", value="1234567890")
    branch_code = b3.text_input("Branch Code", value="470010")
    include_vat = st.checkbox("Add VAT 15%", value=True)
    notes = st.text_area("Notes (Full - No Cut Off)", value="Thank you for your business. Please pay within 7 days.")

    if st.button("🧾 GENERATE PRO PDF INVOICE", use_container_width=True):
        pdf_data = {
            "business_name": business_name, "business_address": business_address,
            "business_phone": business_phone, "business_email": business_email,
            "vat_no": vat_no, "invoice_no": invoice_no,
            "invoice_date": invoice_date, "due_date": due_date,
            "client_name": client_name, "client_address": client_address,
            "client_phone": client_phone, "client_email": client_email,
            "items": items, "bank_name": bank_name, "account_no": account_no,
            "branch_code": branch_code, "include_vat": include_vat, "notes": notes,
        }
        pdf_bytes, total = generate_invoice_pdf(pdf_data)
        st.success(f"PRO Invoice Generated! Total Due: R {total:,.2f} - Date: {invoice_date}")
        st.download_button("⬇️ DOWNLOAD INVOICE PDF", data=pdf_bytes, file_name=f"{invoice_no}.pdf", mime="application/pdf", use_container_width=True)
        # WhatsApp share hint
        st.info(f"Send on WhatsApp: 'Hi {client_name}, here is Invoice {invoice_no} for R {total:,.2f}, due {due_date}. Thank you - CleanData LAI'")
        st.session_state.invoices.append({"Invoice": invoice_no, "Client": client_name, "Date": invoice_date, "Total": f"R {total:,.2f}"})
