import pandas as pd
import re
import os

# ================= CONFIGURATION =================
INPUT_FILE = "extraction_report.csv"
OUTPUT_FILE = "Final_Voter_List_Parsed.xlsx"
# =================================================

def to_bengali_digits(text):
    """Converts English digits to Bengali digits."""
    if not isinstance(text, str): return ""
    map_digits = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return text.translate(map_digits)

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
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found!")
        return

    print("🚀 Loading Extraction Report...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Check if 'Raw Extracted Text' column exists
    if "Raw Extracted Text" not in df.columns:
        print("Error: Column 'Raw Extracted Text' not found in CSV!")
        return

    print(f"🔄 Parsing {len(df)} rows...")

    parsed_data = []
    
    for index, row in df.iterrows():
        raw_text = row.get("Raw Extracted Text", "")
        
        # Apply Parsing
        parsed_fields = parse_bengali_row(raw_text)
        
        # Add File Info (Page/Box) for reference
        parsed_fields["Page Name"] = row.get("Page Name", "")
        parsed_fields["Box Name"] = row.get("Box Name", "")
        
        parsed_data.append(parsed_fields)

    # Convert to DataFrame
    final_df = pd.DataFrame(parsed_data)

    # Reorder columns nicely
    cols = ["Page Name", "Box Name", "Serial", "Name", "Voter No", "Father/Husband", "Mother", "Occupation", "DOB", "Address"]
    final_df = final_df[cols]

    print("💾 Saving to Excel...")
    final_df.to_excel(OUTPUT_FILE, index=False)
    
    print(f"🎉 SUCCESS! Data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()