import fitz  # PyMuPDF for PDF
from PIL import Image
import pytesseract

# --- NEW FUNCTION TO READ ALL FILE TYPES ---
def read_any_file(uploaded_file):
    name = uploaded_file.name.lower()
    
    # 1. CSV
    if name.endswith('.csv'):
        return pd.read_csv(uploaded_file)
    
    # 2. Excel
    elif name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(uploaded_file)
    
    # 3. PDF - extract text and tables
    elif name.endswith('.pdf'):
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        # Try to make a DataFrame from PDF text
        # Simple: split lines
        lines = [line.split() for line in text.split('\n') if line.strip()]
        if lines:
            return pd.DataFrame(lines)
        else:
            st.error("Could not read PDF - it might be scanned image. Try uploading as Image!")
            return None
    
    # 4. Image JPG/PNG - use OCR to read text
    elif name.endswith(('.png', '.jpg', '.jpeg')):
        image = Image.open(uploaded_file)
        text = pytesseract.image_to_string(image)
        lines = [line.split(',') for line in text.split('\n') if line.strip()]
        if lines:
            # If first line looks like header, use it
            return pd.DataFrame(lines[1:], columns=lines[0] if len(lines[0])>1 else None)
        return pd.DataFrame([text])
    
    else:
        st.error("Unsupported file! Upload CSV, Excel, PDF, JPG, PNG")
        return None

# --- THEN USE IT ---
# Replace: df = pd.read_csv(uploaded_file) or pd.read_excel
# With:
df = read_any_file(uploaded_file)
if df is not None:
    st.success(f"File read! Found {len(df)} rows")
    st.dataframe(df.head())
