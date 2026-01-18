import fitz  # PyMuPDF
from PIL import Image
import os
import shutil

# ================= CONFIGURATION =================
PDF_PATH = "../files/150432_com_112_female_without_photo_7_2025-11-24.pdf" 
OUTPUT_BASE_DIR = "150432_com_112_female_without_photo_7_2025-11-24"
DPI = 400

# 1. Box Dimensions
BOX_W = 1300
BOX_H = 442

# 2. STANDARD PAGE COORDINATES (Page 4 onwards)
# 6 Rows
STD_COLS_X = [375, 1689, 3006]
STD_ROWS_Y = [180, 630, 1080, 1530, 1980, 2430]

# 3. START PAGE COORDINATES (Page 3)
# 5 Rows (Header Area skipped)
START_PAGE_COLS_X = [375, 1689, 3005]
START_PAGE_ROWS_Y = [634, 1085, 1535, 1985, 2435]

# =================================================

def ensure_clean_dir(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

def run_full_extraction():
    print(f"Opening PDF: {PDF_PATH}...")
    try:
        doc = fitz.open(PDF_PATH)
    except Exception as e:
        print(f"Error opening file: {e}")
        return

    print(f"Total Pages: {doc.page_count}")
    print(f"Output Directory: {OUTPUT_BASE_DIR}")
    
    # Reset output folder
    ensure_clean_dir(OUTPUT_BASE_DIR)
    
    total_boxes = 0

    # Loop through ALL pages
    for pno in range(doc.page_count):
        
        # 1. Skip Cover Pages (Page 1 and 2)
        if pno < 2: 
            print(f"Skipping Page {pno + 1} (Cover Page)")
            continue

        # 2. Determine Grid
        if pno == 2: # Page 3 (Start Page)
            cols = START_PAGE_COLS_X
            rows = START_PAGE_ROWS_Y
            layout_name = "Start Page (5 Rows)"
        else: # Page 4+ (Standard)
            cols = STD_COLS_X
            rows = STD_ROWS_Y
            layout_name = "Standard (6 Rows)"

        print(f"Processing Page {pno + 1} [{layout_name}]...", end="\r")

        # 3. Render Page
        page = doc.load_page(pno)
        pix = page.get_pixmap(dpi=DPI, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # 4. Create Folder for this page
        page_dir = os.path.join(OUTPUT_BASE_DIR, f"Page_{pno + 1:03d}")
        os.makedirs(page_dir, exist_ok=True)

        # 5. Crop and Save
        box_count = 1
        for y in rows:
            for x in cols:
                # Crop
                crop = img.crop((x, y, x + BOX_W, y + BOX_H))
                
                # Save
                fname = f"Box_{box_count:02d}.jpg"
                save_path = os.path.join(page_dir, fname)
                crop.save(save_path, quality=85) # Quality 85 is good for review
                
                box_count += 1
                total_boxes += 1
    
    print(f"\n\nDone! Extracted {total_boxes} boxes.")
    print(f"Go to folder '{OUTPUT_BASE_DIR}' to review.")

if __name__ == "__main__":
    run_full_extraction()
