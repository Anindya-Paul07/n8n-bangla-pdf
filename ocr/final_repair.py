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
INPUT_EXCEL = "Final_Voter_List_Perfected.xlsx"
OUTPUT_EXCEL = "Final_Voter_List_Ultimate.xlsx"
CROPS_FOLDER = "full_extraction_dump"                   # Folder with images
GCV_API_KEY = "AIzaSyDVXx-7oVuDFFfB_x0X7D4PI7RgK99Pdrc" 
# =================================================

def build_image_map(root_folder):
    """Maps (Page, Box) -> FilePath to fix path errors"""
    print("⚙️  Mapping images...")
    image_map = {}
    for filepath in glob.glob(os.path.join(root_folder, "**", "*.*"), recursive=True):
        if filepath.lower().endswith(('.jpg', '.jpeg', '.png')):
            try:
                parts = filepath.split(os.sep)
                p_match = re.search(r'(\d+)', parts[-2])
                b_match = re.search(r'(\d+)', parts[-1])
                if p_match and b_match:
                    image_map[(int(p_match.group(1)), int(b_match.group(1)))] = filepath
            except: continue
    return image_map

def call_gcv_api(image_path):
    """Call Google Cloud Vision"""
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
    except: pass
    return ""

def to_bengali_digits(text):
    if not isinstance(text, str): return ""
    return text.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))

def blind_parse(raw_text):
    """
    AGGRESSIVE PARSING:
    Does not look for 'Name:' label. 
    Assumes Name is the text between Serial and Voter ID.
    """
    if not isinstance(raw_text, str): return {}
    
    # Flatten text
    text = raw_text.replace("\n", " ").strip()
    data = {}

    # 1. GET VOTER ID (The Anchor)
    # Find any sequence of 10-18 digits
    voter_match = re.search(r'([0-9০-৯]{10,18})', text)
    
    if voter_match:
        data["Voter No"] = to_bengali_digits(voter_match.group(1))
        
        # SPLIT TEXT: [Before Voter ID] [Voter ID] [After Voter ID]
        parts = text.split(voter_match.group(1))
        before_part = parts[0].strip()
        after_part = parts[1].strip() if len(parts) > 1 else ""

        # 2. GET NAME (Everything before Voter ID, minus the Serial)
        # Remove Serial (3-4 digits at start)
        name_text = re.sub(r'^[0-9০-৯]{3,4}[.\s]*', '', before_part)
        
        # Remove any lingering "Name" labels like "নাম" or "নাম:"
        name_text = re.sub(r'(নাম|ভোটার|এলাকার|নং)[:;\-\s]*', '', name_text).strip()
        
        if name_text:
            data["Name"] = name_text

        # 3. GET FATHER (Immediate text after Voter ID)
        # Look until we hit 'Mother' or 'Occupation'
        father_match = re.search(r'^(.*?)(?=\s+(?:মাতা|পেশা|স্বামী)|$)', after_part)
        if father_match:
            # Clean label "Pita:"
            f_text = re.sub(r'(পিতা|স্বামী)[:;\-\s]*', '', father_match.group(1)).strip()
            data["Father/Husband"] = f_text

    else:
        # Emergency: No Voter ID found? 
        # Just grab the first text block as Name if it looks like words
        pass

    # 4. DOB & Address (Standard Regex still works best for these)
    dob_match = re.search(r'([0-9০-৯]{2}[/.\-][0-9০-৯]{2}[/.\-][0-9০-৯]{4})', text)
    if dob_match: data["DOB"] = to_bengali_digits(dob_match.group(1))
    
    addr_match = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', text)
    if addr_match: data["Address"] = to_bengali_digits(addr_match.group(1).strip())

    return data

def main():
    if not os.path.exists(INPUT_EXCEL):
        print("Input file not found.")
        return

    # Map Images
    image_map = build_image_map(CROPS_FOLDER)

    print("\n🔍 identifying broken rows...")
    df = pd.read_excel(INPUT_EXCEL)
    df.replace(r'^\s*$', np.nan, regex=True, inplace=True)
    
    # Filter broken rows
    mask = df[["Name", "Voter No"]].isna().any(axis=1)
    bad_rows = df[mask].index.tolist()
    
    if not bad_rows:
        print("✅ No broken rows left!")
        return

    print(f"⚠️ Attempting Final Sweep on {len(bad_rows)} rows...")
    
    fixed = 0
    for i, idx in enumerate(bad_rows):
        # Get IDs
        try:
            p_val = str(df.loc[idx, "Page Name"])
            b_val = str(df.loc[idx, "Box Name"])
            p_num = int(re.search(r'(\d+)', p_val).group(1))
            b_num = int(re.search(r'(\d+)', b_val).group(1))
        except: continue

        img_path = image_map.get((p_num, b_num))
        
        print(f"   [{i+1}/{len(bad_rows)}] Page {p_num} Box {b_num}...", end=" ", flush=True)

        if img_path:
            # 1. GCV
            raw_text = call_gcv_api(img_path)
            
            # 2. BLIND PARSE
            extracted = blind_parse(raw_text)
            
            updated = False
            for col in ["Name", "Voter No", "Father/Husband", "DOB", "Address"]:
                if pd.isna(df.loc[idx, col]) and col in extracted and extracted[col]:
                    df.at[idx, col] = extracted[col]
                    updated = True
            
            if updated:
                print("✅ Fixed (Blind Parse)")
                fixed += 1
            else:
                # Save Raw Text to 'Status' column so user can see what's wrong
                print("❌ Failed. Saving raw text to debug.")
                df.at[idx, "Address"] = f"RAW GCV: {raw_text}" # Dump text in Address col if desperate
        else:
            print("❌ Image Missing")
        
        time.sleep(0.5)

    df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"\n🎉 Sweep Complete. Fixed {fixed} rows. Saved to {OUTPUT_EXCEL}")

if __name__ == "__main__":
    main()