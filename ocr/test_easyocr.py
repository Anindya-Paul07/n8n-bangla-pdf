import os
import re
import pandas as pd
import easyocr
import glob
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

# ================= CONFIGURATION =================
CROPS_FOLDER = "150432_com_112_female_without_photo_7_2025-11-24"
OUTPUT_FILE = "150432_com_112_female_without_photo_7_2025-11-24.xlsx"
RAW_CSV_FILE = "raw_ocr_output.csv"
USE_GPU = False  # Set True if you have an NVIDIA GPU
# =================================================

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
    voter_match = re.search(r'ভোটার\s*[:;]?\s*(?:নং)?\s*[:;]?\s*([0-9০-৯]+)', text)
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

    # 8. ADDRESS (Everything after 'ঠিকানা', but stop at 'চট্টগ্রাম')
    addr_match = re.search(r'ঠিকানা\s*[:;]?\s*(.*)', text, re.DOTALL)
    if addr_match:
        clean_addr = addr_match.group(1).replace("\n", " ").strip()
        # Stop at 'চট্টগ্রাম' - include the word but nothing after it
        if 'চট্টগ্রাম' in clean_addr:
            clean_addr = clean_addr.split('চট্টগ্রাম')[0] + 'চট্টগ্রাম'
        data["Address"] = to_bengali_digits(clean_addr)

    return data

# --- WORKER FUNCTION ---
def process_batch(image_files_batch):
    """
    Worker process to handle a batch of images.
    Initializes its own EasyOCR Reader to avoid pickling issues.
    """
    # Initialize reader inside the process
    # Using 'en' and 'bn' as before.
    # gpu=USE_GPU (False for CPU optimization)
    reader = easyocr.Reader(['bn', 'en'], gpu=USE_GPU, verbose=False)
    
    results = []
    
    for img_path in image_files_batch:
        try:
            # Extract basic info from path
            parts = img_path.split(os.sep)
            # Safe extraction of Page/Box numbers
            try:
                p_val = re.search(r'(\d+)', parts[-2]).group(1)
                b_val = re.search(r'(\d+)', parts[-1]).group(1)
            except:
                p_val, b_val = 0, 0
                
            # Perform OCR
            # detail=0 returns simple extracted text list
            # paragraph=True helps combine lines
            ocr_text_list = reader.readtext(img_path, detail=0, paragraph=True)
            
            raw_text = clean_ocr_text(ocr_text_list)
            
            results.append({
                "Page Name": f"Page_{int(p_val):03d}",
                "Box Name": f"Box_{int(b_val):02d}.jpg",
                "Raw Text": raw_text
            })
            
        except Exception as e:
            # Log error but don't crash
            # simplified printing for worker
            results.append({
                "Page Name": f"Page_{int(p_val):03d}", # Fallback
                "Box Name": os.path.basename(img_path),
                "Raw Text": f"ERROR: {str(e)}"
            })
            
    return results

def main():
    if not os.path.exists(CROPS_FOLDER):
        print(f"Error: {CROPS_FOLDER} not found!")
        return

    print("🚀 Starting EasyOCR Extraction (Multiprocessing Optimized)...")
    
    # 1. Collect Images
    image_files = sorted(glob.glob(os.path.join(CROPS_FOLDER, "**", "*.*"), recursive=True))
    image_files = [f for f in image_files if f.lower().endswith(('.jpg', '.png'))]
    
    total = len(image_files)
    if total == 0:
        print("No images found.")
        return
        
    print(f"Found {total} images.")

    # 2. Determine CPU Cores and Batches
    num_workers = max(1, os.cpu_count() - 1)  # Leave one core for system/main
    # Alternatively, use all cores provided enough RAM:
    # num_workers = os.cpu_count()
    
    print(f"🔥 Using {num_workers} parallel workers on CPU.")
    
    # Split files into chunks for workers
    chunk_size = (total + num_workers - 1) // num_workers
    batches = [image_files[i:i + chunk_size] for i in range(0, total, chunk_size)]
    
    raw_data_list = []
    
    # 3. Run Multiprocessing
    print("⏳ Processing... (This might take a while, but it's parallelized!)")
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit tasks
        futures = [executor.submit(process_batch, batch) for batch in batches]
        
        # Gather results as they complete
        completed_count = 0
        for future in as_completed(futures):
            try:
                batch_results = future.result()
                raw_data_list.extend(batch_results)
                
                completed_count += len(batch_results)
                print(f"✅ Progress: {completed_count}/{total} images processed.")
            except Exception as e:
                print(f"❌ Worker Error: {e}")

    # 4. Save RAW Data to CSV (sorted by Page and Box)
    print(f"\n💾 Saving Raw Text to {RAW_CSV_FILE}...")
    df_raw = pd.DataFrame(raw_data_list)
    # Sort by Page Name and Box Name to maintain sequential order
    df_raw = df_raw.sort_values(by=["Page Name", "Box Name"], ignore_index=True)
    df_raw.to_csv(RAW_CSV_FILE, index=False, encoding="utf-8-sig")

    # 5. Parse Data from CSV
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

    # 6. Save Final Excel
    df_final = pd.DataFrame(final_data_list)
    
    # Ensure columns exist
    cols = ["Page Name", "Box Name", "Serial", "Name", "Voter No", "Father/Husband", "Mother", "Occupation", "DOB", "Address", "Raw Text"]
    for c in cols:
        if c not in df_final.columns:
            df_final[c] = ""
            
    df_final = df_final[cols] # Reorder
    
    # Sort by Page Name and Box Name to maintain sequential order
    df_final = df_final.sort_values(by=["Page Name", "Box Name"], ignore_index=True)

    df_final.to_excel(OUTPUT_FILE, index=False)
    print(f"🎉 DONE! Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    # Required for Windows multiprocessing
    multiprocessing.freeze_support()
    main()