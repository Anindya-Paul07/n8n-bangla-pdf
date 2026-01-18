import os
import re
import pandas as pd
import easyocr
import glob
import logging

# ================= CONFIGURATION =================
CROPS_FOLDER = "full_extraction_dump" 
OUTPUT_FILE = "Final_Voter_List_EasyOCR.xlsx"
USE_GPU = False # Set True if you have an NVIDIA GPU
# =================================================

# Initialize EasyOCR Reader for Bengali ('bn') and English ('en')
# English is added because numbers (150...) often appear in English
print("⏳ Loading EasyOCR Model...")
reader = easyocr.Reader(['bn', 'en'], gpu=USE_GPU, verbose=False)
print("✅ Model Loaded!")

def to_bengali_digits(text):
    if not isinstance(text, str): return ""
    return text.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))

def clean_ocr_text(text_list):
    """
    EasyOCR returns a list of strings directly.
    """
    if not text_list: return ""
    return " ".join(text_list).replace("|", " ").replace("I", " ")

def parse_bengali_row(text):
    """
    Extracts fields using strict Bengali keyword patterns.
    """
    if not isinstance(text, str) or not text.strip():
        return {}

    data = {
        "Serial": "",
        "Name": "",
        "Voter No": "",
        "Father/Husband": "",
        "Mother": "",
        "Occupation": "",
        "DOB": "",
        "Address": ""
    }

    # 1. SERIAL (Start of string, looks for 3-4 digits followed by dot/space)
    # Matches: "0001. " or "০০০১ "
    serial_match = re.search(r'^.*?([0-9০-৯]{3,4})[.\s]', text)
    if serial_match:
        data["Serial"] = to_bengali_digits(serial_match.group(1))

    # 2. NAME (From 'নাম' to 'ভোটার')
    name_match = re.search(r'নাম\s*[:;]?\s*(.*?)(?=\s+ভোটার)', text)
    if name_match:
        data["Name"] = name_match.group(1).strip()

    # 3. VOTER NO (From 'ভোটার নং' to 'পিতা' OR 'স্বামী')
    voter_match = re.search(r'ভোটার\s*নং\s*[:;]?\s*([0-9০-৯]+)', text)
    if voter_match:
        data["Voter No"] = to_bengali_digits(voter_match.group(1))

    # 4. FATHER / HUSBAND (From 'পিতা'/'স্বামী' to 'মাতা')
    fh_match = re.search(r'(?:পিতা|স্বামী)\s*[:;]?\s*(.*?)(?=\s+মাতা)', text)
    if fh_match:
        data["Father/Husband"] = fh_match.group(1).strip()

    # 5. MOTHER (From 'মাতা' to 'পেশা')
    mother_match = re.search(r'মাতা\s*[:;]?\s*(.*?)(?=\s+পেশা)', text)
    if mother_match:
        data["Mother"] = mother_match.group(1).strip()

    # 6. OCCUPATION (From 'পেশা' to 'জন্ম')
    occ_match = re.search(r'পেশা\s*[:;]?\s*(.*?)(?=[,;]?\s*জন্ম)', text)
    if occ_match:
        data["Occupation"] = occ_match.group(1).strip()

    # 7. DOB (From 'জন্ম তারিখ' to 'ঠিকানা')
    # Looks for pattern like 10/07/1967
    dob_match = re.search(r'জন্ম\s*তারিখ\s*[:;]?\s*([0-9০-৯/.-]+)', text)
    if dob_match:
        data["DOB"] = to_bengali_digits(dob_match.group(1))

    # 8. ADDRESS (Everything after 'ঠিকানা')
    addr_match = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', text, re.DOTALL)
    if addr_match:
        clean_addr = addr_match.group(1).replace("\n", " ").strip()
        data["Address"] = to_bengali_digits(clean_addr)

    return data

def main():
    if not os.path.exists(CROPS_FOLDER):
        print(f"Error: {CROPS_FOLDER} not found!")
        return

    print("🚀 Starting EasyOCR Extraction...")
    raw_data_list = []
    
    # Recursive search for images
    image_files = sorted(glob.glob(os.path.join(CROPS_FOLDER, "**", "*.*"), recursive=True))
    image_files = [f for f in image_files if f.lower().endswith(('.jpg', '.png'))]
    
    total = len(image_files)
    print(f"Found {total} images.")

    for i, img_path in enumerate(image_files):
        try:
            parts = img_path.split(os.sep)
            p_val = re.search(r'(\d+)', parts[-2]).group(1)
            b_val = re.search(r'(\d+)', parts[-1]).group(1)
        except:
            p_val, b_val = 0, 0

        print(f"[{i+1}/{total}] Processing Page {p_val} Box {b_val}...", end=" ", flush=True)

        try:
            # --- RUN EASYOCR ---
            # detail=0 returns only the text list, no bounding boxes
            result_list = reader.readtext(img_path, detail=0, paragraph=True)
            
            if result_list:
                raw_text = clean_ocr_text(result_list)
                
                raw_data_list.append({
                    "Page Name": f"Page_{int(p_val):03d}",
                    "Box Name": f"Box_{int(b_val):02d}.jpg",
                    "Raw Text": raw_text
                })
                print("✅")
            else:
                print("❌ Empty")
                raw_data_list.append({
                    "Page Name": f"Page_{int(p_val):03d}",
                    "Box Name": f"Box_{int(b_val):02d}.jpg",
                    "Raw Text": ""
                })

        except Exception as e:
            print(f"❌ Error: {e}")

    # 1. Save RAW Data to CSV
    RAW_CSV = "raw_ocr_output.csv"
    print(f"\n💾 Saving Raw Text to {RAW_CSV}...")
    df_raw = pd.DataFrame(raw_data_list)
    df_raw.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")

    # 2. Parse Data from CSV
    print("🔄 Parsing Raw Text...")
    final_data_list = []
    
    for _, row in df_raw.iterrows():
        raw_text = str(row.get("Raw Text", ""))
        parsed_row = parse_bengali_row(raw_text)
        
        # Attach Metadata
        parsed_row["Page Name"] = row["Page Name"]
        parsed_row["Box Name"] = row["Box Name"]
        parsed_row["Raw Text"] = raw_text
        
        final_data_list.append(parsed_row)

    # 3. Save Final Excel
    df_final = pd.DataFrame(final_data_list)
    
    # Ensure columns exist
    cols = ["Page Name", "Box Name", "Serial", "Name", "Voter No", "Father/Husband", "Mother", "Occupation", "DOB", "Address", "Raw Text"]
    for c in cols:
        if c not in df_final.columns:
            df_final[c] = ""
            
    df_final = df_final[cols] # Reorder

    df_final.to_excel(OUTPUT_FILE, index=False)
    print(f"🎉 DONE! Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()