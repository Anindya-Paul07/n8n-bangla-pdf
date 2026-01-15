import base64
import requests
import json
import os
import csv

# ================= CONFIGURATION =================
API_KEY = "AIzaSyDVXx-7oVuDFFfB_x0X7D4PI7RgK99Pdrc" 
MAIN_DATA_FOLDER = "full_extraction_dump"  # Folder containing 'Page_1', 'Page_2', etc.
OUTPUT_DOCUMENT = "extraction_report.csv"
URL = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
# =================================================

def extract_text_from_image(image_path):
    """Sends image to GCV with Bengali Language Hint"""
    try:
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        payload = {
            "requests": [
                {
                    "image": {"content": base64_image},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    "imageContext": {
                        "languageHints": ["bn"]  # <--- CRITICAL: Forces Bengali
                    }
                }
            ]
        }

        response = requests.post(URL, json=payload, timeout=10)
        result = response.json()

        if "responses" in result and result["responses"][0]:
            text_annotation = result["responses"][0].get("fullTextAnnotation")
            if text_annotation:
                # Replace newlines with spaces to keep CSV clean
                return text_annotation["text"].replace("\n", " ").strip()
        return ""

    except Exception as e:
        return f"Error: {e}"

def main():
    if not os.path.exists(MAIN_DATA_FOLDER):
        print(f"Error: Folder '{MAIN_DATA_FOLDER}' not found!")
        return

    # Create/Open the CSV file
    with open(OUTPUT_DOCUMENT, mode='w', newline='', encoding='utf-8-sig') as csv_file:
        writer = csv.writer(csv_file)
        # Write Header
        writer.writerow(["Page Name", "Box Name", "Raw Extracted Text"])

        # Get sorted list of page folders
        subfolders = sorted([f for f in os.listdir(MAIN_DATA_FOLDER) if os.path.isdir(os.path.join(MAIN_DATA_FOLDER, f))])

        print(f"🚀 Starting extraction on {len(subfolders)} folders...")
        print(f"💾 Saving data to: {OUTPUT_DOCUMENT}\n")

        total_boxes = 0

        for folder_name in subfolders:
            folder_path = os.path.join(MAIN_DATA_FOLDER, folder_name)
            
            # Get sorted images
            images = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            
            if not images:
                continue

            print(f"📂 Processing {folder_name} ({len(images)} boxes)...")

            for filename in images:
                image_path = os.path.join(folder_path, filename)
                
                # 1. Extract
                raw_text = extract_text_from_image(image_path)
                
                # 2. Save to CSV
                writer.writerow([folder_name, filename, raw_text])
                
                # Optional: Print to console to see it working
                # print(f"   - {filename}: {raw_text[:30]}...") 
                total_boxes += 1

    print(f"\n🎉 DONE! Extracted {total_boxes} boxes.")
    print(f"📄 Data saved in: {OUTPUT_DOCUMENT}")

if __name__ == "__main__":
    main()