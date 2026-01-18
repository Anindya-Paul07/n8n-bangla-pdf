import os
import re
import pandas as pd
from paddleocr import PaddleOCR
import glob
import logging

# ================= CONFIGURATION =================
CROPS_FOLDER = "full_extraction_dump" 
OUTPUT_FILE = "Final_Voter_List_Paddle.xlsx"
# =================================================

# --- THE FIX: Use 'bn' instead of 'ben' ---
try:
    print("⏳ Loading PaddleOCR model for Bengali (bn)...")
    ocr = PaddleOCR(use_angle_cls=True, lang='bn', use_gpu=False, show_log=False)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit()

# Suppress warnings
logging.getLogger("ppocr").setLevel(logging.ERROR)

def to_bengali_digits(text):
    if not isinstance(text, str): return ""
    return text.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))

def clean_ocr_text(text_list):
    if not text_list: return ""
    full_text = " ".join([line[1][0] for line in text_list])
    full_text = full_text.replace("|", " ").replace("I", " ")
    return full_text

def parse_data(raw_text):
    data = {}
    text = raw_text.replace("\n", " ")

    # 1. SERIAL
    m = re.search(r'^.*?([0-9০-৯]{3,4})', text)
    if m: data["Serial"] = to_bengali_digits(m.group(1))

    # 2. NAME
    m = re.search(r'নাম\s*[:;]?\s*(.*?)(?=\s+(?:ভোটার|পিতা|স্বামী)|$)', text)
    if m: data["Name"] = m.group(1).strip()

    # 3. VOTER NO
    m = re.search(r'ভোটার\s*[:;]?\s*(?:নং)?\s*[:;]?\s*([0-9০-৯a-zA-Z]+)', text)
    if m:
        data["Voter No"] = to_bengali_digits(m.group(1))
    else:
        # Fallback regex for long numbers
        nums = re.findall(r'[0-9০-৯]{10,18}', text)
        if nums: data["Voter No"] = to_bengali_digits(nums[0])

    # 4. FATHER/HUSBAND
    m = re.search(r'(?:পিতা|স্বামী)\s*[:;]?\s*(.*?)(?=\s+মাতা|$)', text)
    if m: data["Father/Husband"] = m.group(1).strip()

    # 5. MOTHER
    m = re.search(r'মাতা\s*[:;]?\s*(.*?)(?=\s+পেশা|$)', text)
    if m: data["Mother"] = m.group(1).strip()

    # 6. OCCUPATION
    m = re.search(r'পেশা\s*[:;]?\s*(.*?)(?=\s+জন্ম|$)', text)
    if m: data["Occupation"] = m.group(1).strip()

    # 7. DOB
    m = re.search(r'([0-9০-৯]{2}[/.\-][0-9০-৯]{2}[/.\-][0-9০-৯]{4})', text)
    if m: data["DOB"] = to_bengali_digits(m.group(1))

    # 8. ADDRESS
    m = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', text)
    if m: data["Address"] = to_bengali_digits(m.group(1).strip())

    return data

def main():
    if not os.path.exists(CROPS_FOLDER):
        print(f"Error: {CROPS_FOLDER} not found!")
        return

    print("🚀 Starting Extraction...")
    
    all_data = []
    image_files = sorted(glob.glob(os.path.join(CROPS_FOLDER, "**", "*.*"), recursive=True))
    image_files = [f for f in image_files if f.lower().endswith(('.jpg', '.png'))]
    
    total = len(image_files)
    print(f"Found {total} images.")

    for i, img_path in enumerate(image_files):
        # Extract ID info
        try:
            parts = img_path.split(os.sep)
            p_val = re.search(r'(\d+)', parts[-2]).group(1)
            b_val = re.search(r'(\d+)', parts[-1]).group(1)
        except:
            p_val, b_val = 0, 0

        print(f"[{i+1}/{total}] Processing Page {p_val} Box {b_val}...", end=" ", flush=True)

        try:
            result = ocr.ocr(img_path, cls=True)
            
            if result and result[0]:
                raw_text = clean_ocr_text(result[0])
                extracted = parse_data(raw_text)
                
                extracted["Page Name"] = f"Page_{int(p_val):03d}"
                extracted["Box Name"] = f"Box_{int(b_val):02d}.jpg"
                extracted["Raw Text"] = raw_text 
                
                all_data.append(extracted)
                print("✅")
            else:
                print("❌ Empty")
                all_data.append({"Page Name": f"Page_{int(p_val):03d}", "Box Name": f"Box_{int(b_val):02d}.jpg", "Status": "Failed"})

        except Exception as e:
            print(f"❌ {e}")

    df = pd.DataFrame(all_data)
    cols = ["Page Name", "Box Name", "Serial", "Name", "Voter No", "Father/Husband", "Mother", "Occupation", "DOB", "Address", "Raw Text"]
    for c in cols:
        if c not in df.columns: df[c] = ""
    
    df[cols].to_excel(OUTPUT_FILE, index=False)
    print(f"\n🎉 DONE! Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()