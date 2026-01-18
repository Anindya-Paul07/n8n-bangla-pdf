import fitz  # PyMuPDF
import cv2
import numpy as np
import os

# ================= CONFIGURATION =================
PDF_PATH = "../files/150397_com_2833_male_without_photo_160_2025-11-24.pdf"   # <--- RENAME THIS
PAGE_NO = 4                       # Page to test
DPI = 400
SHIFT_AMOUNT = 30                 # How many pixels to shift for testing

# ORIGINAL COORDINATES
BOX_W, BOX_H = 1296, 430
STD_COLS = [375, 1689, 3006]
STD_ROWS = [234, 684, 1134, 1584, 2034, 2484]
# ==============================================

def generate_grid_image(doc, x_shift, y_shift, label):
    page = doc.load_page(PAGE_NO)
    pix = page.get_pixmap(dpi=DPI, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Apply Shift
    current_cols = [x + x_shift for x in STD_COLS]
    current_rows = [y + y_shift for y in STD_ROWS]

    # Draw Boxes
    for y in current_rows:
        for x in current_cols:
            cv2.rectangle(img, (x, y), (x + BOX_W, y + BOX_H), (0, 0, 255), 4)

    # Label the image
    cv2.putText(img, label, (100, 150), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 0, 0), 5)
    
    filename = f"check_{label}.jpg"
    cv2.imwrite(filename, img)
    print(f"   📸 Saved: {filename}")

def main():
    if not os.path.exists(PDF_PATH):
        print("Error: PDF not found.")
        return

    print(f"Generating calibration images from {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)

    # Generate 5 Variations
    generate_grid_image(doc, 0, 0, "ORIGINAL")
    generate_grid_image(doc, -SHIFT_AMOUNT, 0, "MOVED_LEFT")
    generate_grid_image(doc, SHIFT_AMOUNT, 0, "MOVED_RIGHT")
    generate_grid_image(doc, 0, -SHIFT_AMOUNT, "MOVED_UP")
    generate_grid_image(doc, 0, SHIFT_AMOUNT, "MOVED_DOWN")

    print("\n✅ DONE! Open the folder and look at the 5 images.")
    print("👉 Use the instructions below to update your main script.")

if __name__ == "__main__":
    main()