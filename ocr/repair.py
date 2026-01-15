import pandas as pd
import requests
import base64
import json
import os
import re
import glob
import time
import numpy as np

# ================= CONFIGURATION =================
# 1. Files
INPUT_EXCEL = "Final_Voter_List_Parsed.xlsx"  # The file with gaps
REPORT_CSV = "extraction_report.csv"          # The file with raw text (Free Source)
OUTPUT_EXCEL = "Final_Voter_List_Perfected.xlsx"
CROPS_FOLDER = "full_extraction_dump"                   # Folder with images

# 2. Google Cloud Vision Key (Only used if Level 1 fails)
GCV_API_KEY = "AIzaSyDVXx-7oVuDFFfB_x0X7D4PI7RgK99Pdrc" 
# =================================================

def to_bengali_digits(text):
    """Converts 0-9 to ০-৯"""
    if not isinstance(text, str): return ""
    return text.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))

def clean_text(text):
    """Fixes common OCR typos for Regex"""
    if not isinstance(text, str): return ""
    text = text.replace("\n", " ").replace("|", " ").replace("I", " ")
    text = text.replace("নাম-", "নাম:").replace("পিতা-", "পিতা:").replace("মাতা-", "মাতা:")
    return text.strip()

def robust_parse(raw_text):
    """
    Extracts fields even if formatting is bad.
    """
    raw_text = clean_text(raw_text)
    data = {}

    # 1. SERIAL
    m = re.search(r'^.*?([0-9০-৯]{3,4})', raw_text)
    if m: data["Serial"] = to_bengali_digits(m.group(1))

    # 2. NAME (Grab everything between 'Name' and next keyword)
    m = re.search(r'নাম\s*[:;]?\s*(.*?)(?=\s+(?:ভোটার|পিতা|স্বামী)|$)', raw_text)
    if m: data["Name"] = m.group(1).strip()

    # 3. VOTER NO (Try Label -> Fallback to Digits)
    m = re.search(r'ভোটার\s*নং\s*[:;]?\s*([0-9০-৯a-zA-Z]+)', raw_text)
    if m:
        data["Voter No"] = to_bengali_digits(m.group(1))
    else:
        # Fallback: Find 10-18 digit number
        nums = re.findall(r'[0-9০-৯]{10,18}', raw_text)
        if nums: data["Voter No"] = to_bengali_digits(nums[0])

    # 4. FATHER/HUSBAND
    m = re.search(r'(?:পিতা|স্বামী)\s*[:;]?\s*(.*?)(?=\s+মাতা|$)', raw_text)
    if m: data["Father/Husband"] = m.group(1).strip()

    # 5. MOTHER
    m = re.search(r'মাতা\s*[:;]?\s*(.*?)(?=\s+পেশা|$)', raw_text)
    if m: data["Mother"] = m.group(1).strip()

    # 6. OCCUPATION
    m = re.search(r'পেশা\s*[:;]?\s*(.*?)(?=\s+জন্ম|$)', raw_text)
    if m: data["Occupation"] = m.group(1).strip()

    # 7. DOB
    m = re.search(r'([0-9০-৯]{2}[/.\-][0-9০-৯]{2}[/.\-][0-9০-৯]{4})', raw_text)
    if m: data["DOB"] = to_bengali_digits(m.group(1))

    # 8. ADDRESS
    m = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', raw_text)
    if m: data["Address"] = to_bengali_digits(m.group(1).strip())

    return data

def build_maps(report_file, image_folder):
    """
    Creates two maps to find data instantly:
    1. Text Map: (Page, Box) -> Raw Text (from Report)
    2. Image Map: (Page, Box) -> File Path (from Folder)
    """
    print("⚙️  Indexing Report and Images...")
    
    # 1. Build Text Map from CSV
    text_map = {}
    try:
        rep_df = pd.read_csv(report_file)
        for _, row in rep_df.iterrows():
            try:
                # Convert "Page_003" -> 3
                p_num = int(re.search(r'(\d+)', str(row['Page Name'])).group(1))
                b_num = int(re.search(r'(\d+)', str(row['Box Name'])).group(1))
                text_map[(p_num, b_num)] = str(row['Raw Extracted Text'])
            except: continue
        print(f"   ✅ Loaded {len(text_map)} text entries from Report.")
    except Exception as e:
        print(f"   ⚠️ Could not read report: {e}")

    # 2. Build Image Map from Folder
    image_map = {}
    count = 0
    for filepath in glob.glob(os.path.join(image_folder, "**", "*.*"), recursive=True):
        if filepath.lower().endswith(('.jpg', '.jpeg', '.png')):
            try:
                parts = filepath.split(os.sep)
                # Find numbers in folder/filename
                p_match = re.search(r'(\d+)', parts[-2]) # Folder
                b_match = re.search(r'(\d+)', parts[-1]) # File
                if p_match and b_match:
                    image_map[(int(p_match.group(1)), int(b_match.group(1)))] = filepath
                    count += 1
            except: continue
    print(f"   ✅ Indexed {count} images from Disk.")
    
    return text_map, image_map

def call_gcv_api(image_path):
    """Sends image to Google Cloud Vision"""
    if not os.path.exists(image_path): return ""
    try:
        with open(image_path, "rb") as image_file:
            content = base64.b64encode(image_file.read()).decode("utf-8")
        
        url = f"https://vision.googleapis.com/v1/images:annotate?key={GCV_API_KEY}"
        payload = {
            "requests": [{
                "image": {"content": content},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": ["bn"]}
            }]
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "responses" in data and data["responses"][0]:
            return data["responses"][0].get("fullTextAnnotation", {}).get("text", "")
    except Exception as e:
        print(f"   ❌ GCV API Error: {e}")
    return ""

def main():
    if not os.path.exists(INPUT_EXCEL):
        print("Error: Input Excel not found.")
        return

    # 1. SETUP
    text_map, image_map = build_maps(REPORT_CSV, CROPS_FOLDER)
    
    print("\n🔍 Analyzing Input Excel...")
    df = pd.read_excel(INPUT_EXCEL)
    
    # Clean empty cells to NaN
    df.replace(r'^\s*$', np.nan, regex=True, inplace=True)
    
    # Identify Missing Data Rows
    # We check if Name OR Voter No is missing
    mask = df[["Name", "Voter No"]].isna().any(axis=1)
    bad_rows = df[mask].index.tolist()
    
    if not bad_rows:
        print("✅ Data is already perfect!")
        return

    print(f"⚠️ Found {len(bad_rows)} rows with missing Name or Voter No.")
    
    # ================= LEVEL 1: FREE REPAIR (REPORT CSV) =================
    print("\n🚀 Starting Level 1: Repair from Report (Free)...")
    fixed_l1 = 0
    gcv_queue = []

    for idx in bad_rows:
        try:
            # Extract ID
            p_val = str(df.loc[idx, "Page Name"])
            b_val = str(df.loc[idx, "Box Name"])
            p_num = int(re.search(r'(\d+)', p_val).group(1))
            b_num = int(re.search(r'(\d+)', b_val).group(1))
        except:
            continue # Skip invalid rows

        # Check Report
        raw_text = text_map.get((p_num, b_num))
        repaired = False
        
        if raw_text:
            # Parse the text from the report
            extracted = robust_parse(raw_text)
            
            # Fill gaps
            for col in ["Name", "Voter No", "Father/Husband", "Mother", "DOB", "Address"]:
                if pd.isna(df.loc[idx, col]) and col in extracted and extracted[col]:
                    df.at[idx, col] = extracted[col]
                    repaired = True
            
            if repaired:
                # Check if it is FULLY fixed (Name & Voter No present)
                if not pd.isna(df.loc[idx, "Name"]) and not pd.isna(df.loc[idx, "Voter No"]):
                    fixed_l1 += 1
                else:
                    gcv_queue.append((idx, p_num, b_num)) # Partially fixed, still needs GCV
            else:
                gcv_queue.append((idx, p_num, b_num)) # Regex found nothing
        else:
            gcv_queue.append((idx, p_num, b_num)) # No text in report

    print(f"   ✅ Level 1 Complete. Fixed {fixed_l1} rows using Report.")

    # ================= LEVEL 2: PAID REPAIR (GCV) =================
    if gcv_queue:
        print(f"\n⚠️ {len(gcv_queue)} rows are still missing data.")
        confirm = input(">> Repair remaining using Google Cloud Vision? (yes/no): ").lower()
        
        if confirm in ["y", "yes"]:
            print("🚀 Starting Level 2: GCV Repair...")
            fixed_l2 = 0
            
            for i, (idx, p_num, b_num) in enumerate(gcv_queue):
                img_path = image_map.get((p_num, b_num))
                
                print(f"   [{i+1}/{len(gcv_queue)}] Page {p_num} Box {b_num}...", end=" ", flush=True)
                
                if img_path:
                    # Call API
                    new_text = call_gcv_api(img_path)
                    if new_text:
                        extracted = robust_parse(new_text)
                        
                        updated = False
                        for col in ["Name", "Voter No", "Father/Husband", "Mother", "DOB", "Address"]:
                            if pd.isna(df.loc[idx, col]) and col in extracted and extracted[col]:
                                df.at[idx, col] = extracted[col]
                                updated = True
                        
                        if updated:
                            print("✅ Fixed")
                            fixed_l2 += 1
                        else:
                            print("⚠️ Text found but regex failed")
                    else:
                        print("❌ GCV Empty")
                else:
                    print("❌ Image Not Found")
                
                time.sleep(0.5)
                
            print(f"   ✅ Level 2 Complete. Fixed {fixed_l2} rows.")

    # Save
    df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"\n🎉 DONE! Final Data Saved: {OUTPUT_EXCEL}")

if __name__ == "__main__":
    main()