import pytesseract
from PIL import Image
import os

# ================= CONFIGURATION =================
# 1. Path to your crops folder (Convert Windows path to WSL path)
# Example: If on Windows it is "C:\Users\Anindya\Project\crops"
# In WSL it is: "/mnt/c/Users/Anindya/Project/crops"
# Use "." if the folder is inside WSL current directory
IMAGE_FOLDER = "/home/anindya/project/n8n-bangla-pdf/ocr/full_extraction_dump/Page_014" 

# 2. Tesseract Command
# In Linux/WSL, we usually don't need to specify the full path if installed via apt
# But if needed, it is /usr/bin/tesseract
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' 

# 3. Language
LANG = "ben+eng"
# =================================================

def run_test():
    if not os.path.exists(IMAGE_FOLDER):
        print(f"Error: Folder '{IMAGE_FOLDER}' not found.")
        return

    print(f"Testing Tesseract in WSL on: {IMAGE_FOLDER}\n")

    files = sorted([f for f in os.listdir(IMAGE_FOLDER) if f.endswith(".jpg")])[:5]
    
    if not files:
        print("No images found.")
        return

    for filename in files:
        image_path = os.path.join(IMAGE_FOLDER, filename)
        try:
            text = pytesseract.image_to_string(Image.open(image_path), lang=LANG, config="--psm 6")
            print(f"--- {filename} ---")
            print(text.strip())
            print("-" * 30)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
