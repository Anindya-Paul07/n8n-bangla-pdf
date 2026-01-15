import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import os

# ================= USER CONFIGURATION =================
PDF_PATH = "../files/150396_com_3448_male_without_photo_193_2025-11-24.pdf" 
OUTPUT_DIR = "final_verification_crops"
DPI = 400

# 1. Box Size (From your previous measurement)
BOX_W = 1305
BOX_H = 442

# 2. STANDARD PAGE COORDINATES (Page 4, 5, 6...)
# Your measurements: X=[375, 1689, 3006], Y=[234, 684, 1134, 1584, 2034, 2484]
STD_COLS_X = [375, 1689, 3006]
STD_ROWS_Y = [234, 684, 1134, 1584, 2034, 2484]

# 3. START PAGE COORDINATES (Page 3)
# Your measurements: X=[375, 1689, 3005], Y=[634, 1085, 1535, 1985, 2435]
START_PAGE_COLS_X = [375, 1689, 3005]
START_PAGE_ROWS_Y = [634, 1085, 1535, 1985, 2435]

# ======================================================

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def draw_debug_map(img, cols, rows, page_num):
    debug_img = img.copy()
    draw = ImageDraw.Draw(debug_img)
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except:
        font = None

    box_id = 1
    for y in rows:
        for x in cols:
            # Draw Thick Red Box
            draw.rectangle([x, y, x + BOX_W, y + BOX_H], outline="red", width=8)
            # Label
            draw.text((x+30, y+30), f"Box {box_id}", fill="red", font=font)
            
            box_id += 1
            
    save_path = f"{OUTPUT_DIR}/Page_{page_num}_DEBUG_MAP.jpg"
    debug_img.save(save_path)
    print(f" [✓] Map Saved: {save_path}")

def run_test():
    ensure_dir(OUTPUT_DIR)
    doc = fitz.open(PDF_PATH)
    
    # Test Page 3 (Start Page) and Page 4 (Standard)
    # 0-indexed: Page 3 is index 2, Page 4 is index 3
    test_indices = [2, 3] 
    
    for pno in test_indices: 
        if pno >= doc.page_count: continue
        
        print(f"\nProcessing Page {pno + 1}...")
        page = doc.load_page(pno)
        pix = page.get_pixmap(dpi=DPI, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Select Coordinate Set
        if pno == 2: # Start Page
            current_cols = START_PAGE_COLS_X
            current_rows = START_PAGE_ROWS_Y
            print(f" -> Using START PAGE Layout (5 Rows)")
        else: # Standard Page
            current_cols = STD_COLS_X
            current_rows = STD_ROWS_Y
            print(f" -> Using STANDARD Layout (6 Rows)")
            
        # Draw Map
        draw_debug_map(img, current_cols, current_rows, pno + 1)
        
        # Save individual crops for verification
        count = 1
        for y in current_rows:
            for x in current_cols:
                crop = img.crop((x, y, x + BOX_W, y + BOX_H))
                fname = f"Page_{pno+1}_Box_{count:02d}.jpg"
                crop.save(os.path.join(OUTPUT_DIR, fname))
                count += 1

    print(f"\nDone! Check '{OUTPUT_DIR}'.")

if __name__ == "__main__":
    run_test()