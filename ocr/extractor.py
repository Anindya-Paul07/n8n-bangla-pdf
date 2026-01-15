import os
import re
import json
import base64
import requests
import fitz  # PyMuPDF
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from io import BytesIO

# ================= CONFIGURATION =================
PDF_PATH = "../files/current_voter_list.pdf"
GCV_API_KEY = "AIzaSyDVXx-7oVuDFFfB_x0X7D4PI7RgK99Pdrc"  # <--- PASTE KEY HERE
OUTPUT_CSV = "Final_Voter_List_Regex.csv"

# CONSTANTS
DPI = 600
BOX_W, BOX_H = 1300, 440
STD_COLS = [375, 1689, 3006]
STD_ROWS = [234, 684, 1134, 1584, 2034, 2484]
START_COLS = [375, 1689, 3005]
START_ROWS = [634, 1085, 1535, 1985, 2435]
# =================================================

def to_bengali_digits(text):
    """Converts English digits to Bengali digits."""
    if not text: return ""
    map_digits = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return text.translate(map_digits)

def preprocess_image(pil_img):
    """Enhances image contrast for better OCR."""
    img = np.array(pil_img)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    clean = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
    return Image.fromarray(clean)

def call_google_vision(pil_img):
    """Sends image to Google Cloud Vision."""
    buff = BytesIO()
    pil_img.save(buff, format="JPEG", quality=90)
    b64_img = base64.b64encode(buff.getvalue()).decode("utf-8")
    
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GCV_API_KEY}"
    payload = {
        "requests": [{
            "image": {"content": b64_img},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
        }]
    }
    try:
        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()
        return data['responses'][0]['fullTextAnnotation']['text']
    except Exception as e:
        # print(f"  [!] GCV Error: {e}") # Uncomment to debug connection errors
        return ""

def parse_with_regex(text):
    """
    Extracts fields using Pattern Matching (Regex).
    Returns a dictionary of fields and a list of missing keys.
    """
    data = {}
    missing = []
    
    # Clean text (fix pipes as danda)
    text = text.replace("|", "।").replace("I", "।")

    # 1. SERIAL (First numbers found)
    serial_match = re.search(r'^.*?([0-9০-৯]{3,4})', text)
    data['Serial'] = to_bengali_digits(serial_match.group(1)) if serial_match else ""
    if not data['Serial']: missing.append("Serial")

    # 2. NAME (Find text after 'নাম')
    name_match = re.search(r'নাম\s*[:;]?\s*([^\n\r]+)', text)
    data['Name'] = name_match.group(1).strip() if name_match else ""
    if not data['Name']: missing.append("Name")

    # 3. VOTER NO (Find long digit sequence)
    # Strategy: Look for 10-18 digits. Avoid the Serial (length 3-4).
    voter_match = re.search(r'([0-9০-৯]{10,18})', text)
    data['Voter No'] = to_bengali_digits(voter_match.group(1)) if voter_match else ""
    if not data['Voter No']: missing.append("Voter No")

    # 4. FATHER / HUSBAND
    fh_match = re.search(r'(পিতা|স্বামী)\s*[:;]?\s*([^\n\r]+)', text)
    data['Father/Husband'] = fh_match.group(2).strip() if fh_match else ""
    
    # 5. MOTHER
    mother_match = re.search(r'মাতা\s*[:;]?\s*([^\n\r]+)', text)
    data['Mother'] = mother_match.group(1).strip() if mother_match else ""
    if not data['Mother']: missing.append("Mother")

    # 6. OCCUPATION
    occ_match = re.search(r'পেশা\s*[:;]?\s*([^\n\r]+)', text)
    # Often Occupation is on the same line as DOB, so we split if needed
    if occ_match:
        raw_occ = occ_match.group(1).split("জন্ম")[0].strip() # Stop if it hits "Jonmo"
        data['Occupation'] = raw_occ
    else:
        data['Occupation'] = ""

    # 7. DOB (Look for date pattern)
    dob_match = re.search(r'([0-9০-৯]{2}[/.\-][0-9০-৯]{2}[/.\-][0-9০-৯]{4})', text)
    data['DOB'] = to_bengali_digits(dob_match.group(1)) if dob_match else ""
    if not data['DOB']: missing.append("DOB")

    # 8. ADDRESS (Everything after 'ঠিকানা')
    addr_match = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', text, re.DOTALL)
    if addr_match:
        data['Address'] = addr_match.group(1).replace("\n", " ").strip()
        data['Address'] = to_bengali_digits(data['Address']) # Ensure house numbers are Bangla
    else:
        data['Address'] = ""
    if not data['Address']: missing.append("Address")

    return data, missing

def main():
    if not os.path.exists(PDF_PATH):
        print(f"Error: {PDF_PATH} not found!")
        return

    doc = fitz.open(PDF_PATH)
    total_pages = doc.page_count
    all_data = []
    
    print(f"🚀 Starting Regex Extraction on {total_pages} pages...")
    
    # Resume Logic (Optional: Checks if csv exists to skip pages)
    start_page = 0
    if os.path.exists(OUTPUT_CSV):
        try:
            existing_df = pd.read_csv(OUTPUT_CSV)
            if not existing_df.empty:
                last_page = existing_df['Page'].max()
                print(f"🔄 Resuming from Page {last_page + 1}...")
                start_page = last_page
                all_data = existing_df.to_dict('records')
        except:
            pass

    for pno in range(start_page, total_pages):
        # Skip covers
        if pno < 2: continue
        
        real_page = pno + 1
        print(f"Processing Page {real_page}...")
        
        cols, rows = (START_COLS, START_ROWS) if pno == 2 else (STD_COLS, STD_ROWS)
        page = doc.load_page(pno)
        pix = page.get_pixmap(dpi=DPI, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        box_id = 1
        page_records = []
        
        for y in rows:
            for x in cols:
                crop = img.crop((x, y, x + BOX_W, y + BOX_H))
                enhanced_crop = preprocess_image(crop)
                
                # 1. Get Raw Text
                raw_text = call_google_vision(enhanced_crop)
                
                # 2. Parse Locally (Regex)
                record, missing_fields = parse_with_regex(raw_text)
                
                # 3. Add Metadata
                record['Page'] = real_page
                record['Box'] = box_id
                record['Raw_Text_Debug'] = raw_text.replace("\n", " | ") # Save raw text to debug later
                
                # 4. Detect Issue
                if len(missing_fields) > 2: # If more than 2 fields are missing, flag it
                     print(f"  ⚠️  Issue Page {real_page} Box {box_id}: Missing {missing_fields}")
                     record['Status'] = "Review Needed"
                else:
                     record['Status'] = "OK"

                page_records.append(record)
                box_id += 1
        
        all_data.extend(page_records)
        
        # Save every 5 pages
        if real_page % 5 == 0:
            pd.DataFrame(all_data).to_csv(OUTPUT_CSV, index=False)
            print(f"  💾 Saved progress to {OUTPUT_CSV}")

    # Final Save
    pd.DataFrame(all_data).to_csv(OUTPUT_CSV, index=False)
    print(f"🎉 Done! Final data saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()