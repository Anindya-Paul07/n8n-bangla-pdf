import os
import base64
import io
from typing import Any, Dict, List, Optional
import fitz  # PyMuPDF
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Bangla PDF Renderer for GCV")

# COORDINATES
DPI = 600
BOX_W, BOX_H = 1300, 442
STD_COLS = [375, 1689, 3006]
STD_ROWS = [234, 684, 1134, 1584, 2034, 2484]
START_COLS = [375, 1689, 3005]
START_ROWS = [634, 1085, 1535, 1985, 2435]

UPLOAD_DIR = "/app/output"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _jpeg_b64_high_quality(pil_img: Image.Image) -> str:
    """
    Convert image to Base64 for Google Cloud Vision.
    No aggressive downscaling needed (GCV supports up to 10MB).
    """
    img = pil_img.copy()
    
    # Optional: Resize only if HUGE (e.g. > 4000px) to save bandwidth
    if img.width > 4000:
        ratio = 4000 / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))

    buf = io.BytesIO()
    # High quality for better OCR
    img.save(buf, format="JPEG", quality=85, optimize=True)
    b = buf.getvalue()
    return base64.b64encode(b).decode("utf-8")

async def _read_pdf_bytes_from_request(request: Request) -> bytes:
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        for _, v in form.items():
            if hasattr(v, "read"):
                return await v.read()
        raise ValueError("No file found in multipart form")
    return await request.body()

# ---------- endpoint ----------

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/render-pages")  # Renamed for clarity
async def render_pages_endpoint(
    request: Request,
    dpi: int = 300,        # Standard for OCR
    start_page: int = 1,
    max_pages: int = 0,    # 0 = all
):
    try:
        pdf_bytes = await _read_pdf_bytes_from_request(request)
        if not pdf_bytes:
            return JSONResponse({"error": "Empty PDF body"}, status_code=400)

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = doc.page_count

        s = max(1, start_page)
        e = total_pages if max_pages in (0, None) else min(total_pages, s - 1 + int(max_pages))

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        pages_out: List[Dict[str, Any]] = []
        for pno in range(s - 1, e):
            page = doc.load_page(pno)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pil_img = _pil_from_pixmap(pix)
            
            # No OCR here! Just image generation.
            image_b64 = _jpeg_b64_high_quality(pil_img)

            pages_out.append({
                "page": pno + 1,
                "image_b64_jpeg": image_b64
            })

        return {
            "meta": {
                "total_pages": total_pages,
                "processed_count": len(pages_out)
            },
            "pages": pages_out,
        }

    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=500)
