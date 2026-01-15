import os
import base64
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form, HTTPException

app = FastAPI(title="Voter Cropper API")

# COORDINATES
DPI = 600
BOX_W, BOX_H = 1300, 442
STD_COLS = [375, 1689, 3006]
STD_ROWS = [234, 684, 1134, 1584, 2034, 2484]
START_COLS = [375, 1689, 3005]
START_ROWS = [634, 1085, 1535, 1985, 2435]

UPLOAD_DIR = "/app/output"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _pil_to_base64(pil_img):
    buff = BytesIO()
    pil_img.save(buff, format="JPEG")
    return base64.b64encode(buff.getvalue()).decode("utf-8")

@app.post("/upload_pdf_path")
async def upload_pdf_path(filename: str = Form(...)):
    """Reads file directly from the shared volume"""
    # Look for the file in the shared folder mapped to /app/output
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        return {"error": f"File not found at {file_path}. Did you save it to ./files first?"}
    
    doc = fitz.open(file_path)
    # Save a reference copy as 'current_voter_list.pdf' for the cropper to use later
    doc.save(os.path.join(UPLOAD_DIR, "current_voter_list.pdf"))
    
    return {"status": "success", "total_pages": doc.page_count, "filename": filename}

@app.get("/get_page_crops/{page_num}")
async def get_page_crops(page_num: int):
    """Returns 18 base64 images for a specific page"""
    file_path = os.path.join(UPLOAD_DIR, "current_voter_list.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="No PDF uploaded yet")

    doc = fitz.open(file_path)
    if page_num < 1 or page_num > doc.page_count:
        raise HTTPException(status_code=400, detail="Page number out of range")

    # 0-index adjustment
    pno = page_num - 1
    
    # Skip covers
    if pno < 2:
        return {"page": page_num, "crops": []}

    cols, rows = (START_COLS, START_ROWS) if pno == 2 else (STD_COLS, STD_ROWS)
    
    page = doc.load_page(pno)
    pix = page.get_pixmap(dpi=DPI, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    crops_data = []
    box_id = 1
    for y in rows:
        for x in cols:
            crop = img.crop((x, y, x + BOX_W, y + BOX_H))
            crops_data.append({
                "box_id": box_id,
                "image_b64": _pil_to_base64(crop)
            })
            box_id += 1
            
    return {"page": page_num, "crops": crops_data}