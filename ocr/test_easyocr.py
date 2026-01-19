"""
Enhanced EasyOCR Script for Bangla Voter ID Data Extraction
============================================================

This script implements LIGHTWEIGHT image preprocessing optimized for
high-quality Bengali (Bangla) text images.

LIGHTWEIGHT PREPROCESSING PIPELINE (5 steps):
---------------------------------------------
1. Grayscale Conversion: Simplifies image data
2. Light Gaussian Blur: Minimal noise removal
3. Mild CLAHE: Gentle contrast enhancement (clipLimit=1.5)
4. Otsu's Binarization: High contrast text/background
5. Minimal Morphological: Light cleanup (1x1 kernel)

⚠️ OPTIMIZED FOR HIGH-QUALITY IMAGES
This version STOPS at morphological operations and SKIPS:
- Skew correction (can distort already-aligned text)
- Resolution scaling (can degrade clear images)  
- Sharpening (unnecessary for clear images)

EASYOCR OPTIMIZATIONS:
---------------------
- Language: Bengali ('bn') + English ('en')
- Decoder: Beam Search (more accurate than greedy)
- Beam Width: 10 (higher = more accurate, slower)
- Paragraph Mode: Combines text lines intelligently

USAGE:
------
1. Set CROPS_FOLDER to your image directory
2. Adjust ENABLE_PREPROCESSING (True/False) to toggle preprocessing
3. Run: python test_easyocr.py

To test preprocessing on a single image:
    python test_easyocr.py --test-preprocess path/to/image.jpg
"""


import os
import re
import pandas as pd
import easyocr
import glob
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import cv2
import numpy as np
from PIL import Image

# ================= CONFIGURATION =================
# ================= CONFIGURATION =================
CROPS_FOLDER = "150432_com_112_female_without_photo_7_2025-11-24"
OUTPUT_FILE = "150432_com_112_female_without_photo_7_2025-11-24.xlsx"
RAW_CSV_FILE = "raw_ocr_output.csv"
USE_GPU = False  # Set True if you have an NVIDIA GPU
ENABLE_PREPROCESSING = False  # DISABLED - Original images work better!
# Set to True only if you have low-quality/blurry images
TARGET_DPI = 300  # Target resolution for OCR (300 is recommended)
# =================================================

def preprocess_image_for_ocr(image_path):
    """
    Lightweight preprocessing pipeline optimized for high-quality Bangla images.
    
    This version is tuned for already-clear images and stops at morphological operations.
    Steps:
    1. Grayscale conversion
    2. Light noise reduction
    3. Mild contrast enhancement (CLAHE) 
    4. Adaptive binarization
    5. Minimal morphological cleanup
    
    Args:
        image_path: Path to the input image
        
    Returns:
        Preprocessed image suitable for OCR
    """
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Unable to read image: {image_path}")
        
        # Step 1: Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Step 2: Very light noise reduction
        # Smaller kernel to preserve text sharpness for already-clear images
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Step 3: Mild contrast enhancement using CLAHE
        # Reduced clipLimit for already-clear images to avoid over-enhancement
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # Step 4: Adaptive Binarization with Otsu's method
        # This creates high contrast between text and background
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Alternative: Use adaptive threshold for images with varying backgrounds
        # Uncomment if Otsu's doesn't work well:
        # binary = cv2.adaptiveThreshold(enhanced, 255, 
        #                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        #                                cv2.THRESH_BINARY, 11, 2)
        
        # Step 5: Minimal morphological operations
        # Very light cleanup - just close small gaps, don't modify character structure
        kernel = np.ones((1, 1), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Return after morphological step (as requested)
        # Skipping: skew correction, scaling, and sharpening
        return morph
        
    except Exception as e:
        logging.error(f"Preprocessing failed for {image_path}: {e}")
        # Return original image if preprocessing fails
        img = cv2.imread(image_path)
        if img is not None:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return None

def test_preprocessing_on_image(image_path, output_dir="preprocessing_test"):
    """
    Test complete OCR pipeline on a single image and save results.
    
    This function:
    1. Saves intermediate preprocessing steps
    2. Runs EasyOCR on original AND preprocessed images
    3. Updates raw_ocr_output.csv with results
    4. Parses the OCR text
    5. Shows comparison of results
    
    Args:
        image_path: Path to test image
        output_dir: Directory to save intermediate results
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"🧪 TESTING COMPLETE OCR PIPELINE")
    print(f"{'='*60}")
    print(f"📁 Input: {image_path}")
    print(f"📁 Output Dir: {output_dir}/")
    print(f"{'='*60}\n")
    
    # ===== STEP 1: Save Preprocessing Steps =====
    print("📸 Saving preprocessing steps...")
    
    # Original
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Error: Could not read image: {image_path}")
        return
    cv2.imwrite(os.path.join(output_dir, "1_original.jpg"), img)
    
    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(os.path.join(output_dir, "2_grayscale.jpg"), gray)
    
    # Denoised (light)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    cv2.imwrite(os.path.join(output_dir, "3_denoised.jpg"), denoised)
    
    # CLAHE enhanced (mild)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    cv2.imwrite(os.path.join(output_dir, "4_clahe_enhanced.jpg"), enhanced)
    
    # Binarized
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite(os.path.join(output_dir, "5_binarized.jpg"), binary)
    
    # Morphological operations (minimal)
    kernel = np.ones((1, 1), np.uint8)
    morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    cv2.imwrite(os.path.join(output_dir, "6_morphological_FINAL.jpg"), morph)
    
    # Final result (should match step 6 now)
    result = preprocess_image_for_ocr(image_path)
    if result is not None:
        cv2.imwrite(os.path.join(output_dir, "7_function_output.jpg"), result)
    
    print("✅ Preprocessing steps saved!\n")
    
    # ===== STEP 2: Run OCR on Both Original and Preprocessed =====
    print("🔍 Running EasyOCR on ORIGINAL image...")
    reader = easyocr.Reader(['bn', 'en'], gpu=USE_GPU, verbose=False)
    
    # OCR on original
    ocr_original = reader.readtext(
        image_path,
        detail=0,
        paragraph=True,
        decoder='beamsearch',
        beamWidth=10,
        batch_size=1
    )
    text_original = clean_ocr_text(ocr_original)
    
    print("✅ Original OCR complete!")
    print(f"📝 Text length: {len(text_original)} characters\n")
    
    # OCR on preprocessed
    print("🔍 Running EasyOCR on PREPROCESSED image...")
    ocr_preprocessed = reader.readtext(
        result,
        detail=0,
        paragraph=True,
        decoder='beamsearch',
        beamWidth=10,
        batch_size=1
    )
    text_preprocessed = clean_ocr_text(ocr_preprocessed)
    
    print("✅ Preprocessed OCR complete!")
    print(f"📝 Text length: {len(text_preprocessed)} characters\n")
    
    # ===== STEP 3: Update raw_ocr_output.csv =====
    print("💾 Updating raw_ocr_output.csv...")
    
    # Prepare test data
    test_data = [
        {
            "Page Name": "TEST_ORIGINAL",
            "Box Name": os.path.basename(image_path),
            "Raw Text": text_original
        },
        {
            "Page Name": "TEST_PREPROCESSED",
            "Box Name": os.path.basename(image_path),
            "Raw Text": text_preprocessed
        }
    ]
    
    # Load existing CSV or create new one
    try:
        if os.path.exists(RAW_CSV_FILE):
            df_existing = pd.read_csv(RAW_CSV_FILE, encoding='utf-8-sig')
            # Remove previous test entries
            df_existing = df_existing[~df_existing['Page Name'].str.startswith('TEST_')]
            # Append new test data
            df_new = pd.concat([pd.DataFrame(test_data), df_existing], ignore_index=True)
        else:
            df_new = pd.DataFrame(test_data)
        
        df_new.to_csv(RAW_CSV_FILE, index=False, encoding='utf-8-sig')
        print(f"✅ Updated {RAW_CSV_FILE}\n")
    except Exception as e:
        print(f"⚠️ Could not update CSV: {e}\n")
    
    # ===== STEP 4: Parse Both Results =====
    print("🔄 Parsing OCR text...")
    
    parsed_original = parse_bengali_row(text_original)
    parsed_preprocessed = parse_bengali_row(text_preprocessed)
    
    print("✅ Parsing complete!\n")
    
    # ===== STEP 5: Display Results =====
    print(f"\n{'='*60}")
    print(f"📊 RESULTS COMPARISON")
    print(f"{'='*60}\n")
    
    print("🔹 ORIGINAL IMAGE OCR:")
    print(f"   Raw Text: {text_original[:100]}..." if len(text_original) > 100 else f"   Raw Text: {text_original}")
    print(f"\n   Parsed Fields:")
    for key, value in parsed_original.items():
        if value:
            print(f"      {key:20s}: {value}")
    
    print(f"\n{'='*60}\n")
    
    print("🔹 PREPROCESSED IMAGE OCR:")
    print(f"   Raw Text: {text_preprocessed[:100]}..." if len(text_preprocessed) > 100 else f"   Raw Text: {text_preprocessed}")
    print(f"\n   Parsed Fields:")
    for key, value in parsed_preprocessed.items():
        if value:
            print(f"      {key:20s}: {value}")
    
    print(f"\n{'='*60}")
    print(f"✅ TEST COMPLETE!")
    print(f"{'='*60}")
    print(f"\n📁 Check '{output_dir}/' for preprocessing steps")
    print(f"📁 Check '{RAW_CSV_FILE}' for OCR results (look for TEST_* rows)")
    print(f"\n💡 Compare the two results above to see preprocessing impact!\n")




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
    Applies preprocessing for better accuracy.
    """
    # Initialize reader inside the process
    # Using 'bn' (Bangla) and 'en' (English)
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
            
            # Apply preprocessing if enabled
            if ENABLE_PREPROCESSING:
                preprocessed_img = preprocess_image_for_ocr(img_path)
                if preprocessed_img is None:
                    raise ValueError("Preprocessing returned None")
                
                # EasyOCR can work with numpy arrays directly
                ocr_input = preprocessed_img
            else:
                # Use original image
                ocr_input = img_path
            
            # Perform OCR with optimized parameters for Bangla
            # detail=0 returns simple text list
            # paragraph=True helps combine lines
            # decoder='beamsearch' provides better accuracy (slower but more accurate)
            # beamWidth higher values = more accurate but slower
            ocr_text_list = reader.readtext(
                ocr_input, 
                detail=0, 
                paragraph=True,
                decoder='beamsearch',
                beamWidth=10,
                batch_size=1
            )
            
            raw_text = clean_ocr_text(ocr_text_list)
            
            results.append({
                "Page Name": f"Page_{int(p_val):03d}",
                "Box Name": f"Box_{int(b_val):02d}.jpg",
                "Raw Text": raw_text
            })
            
        except Exception as e:
            # Log error but don't crash
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
    
    # Check for test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test-preprocess":
        if len(sys.argv) < 3:
            print("Usage: python test_easyocr.py --test-preprocess <image_path>")
            sys.exit(1)
        test_image = sys.argv[2]
        if not os.path.exists(test_image):
            print(f"Error: Image not found: {test_image}")
            sys.exit(1)
        test_preprocessing_on_image(test_image)
    else:
        main()
