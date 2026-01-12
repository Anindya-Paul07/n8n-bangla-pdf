import base64
import io
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
import numpy as np
import cv2
from PIL import Image
import pytesseract
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Bangla PDF OCR")

# ---------- helpers ----------

def _pil_from_pixmap(pix: fitz.Pixmap) -> Image.Image:
    mode = "RGB" if pix.n < 4 else "RGBA"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
    return img

def _preprocess_for_ocr(pil_img: Image.Image) -> np.ndarray:
    """Return OpenCV image optimized for tesseract."""
    img = np.array(pil_img)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # mild denoise
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # adaptive threshold works well on scanned forms
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11
    )
    return thr

def _ocr_image(cv_img: np.ndarray, lang: str, psm: int, oem: int) -> str:
    # preserve_interword_spaces helps tables
    config = f"--oem {oem} --psm {psm} -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(cv_img, lang=lang, config=config)
    return (text or "").strip()

def _jpeg_b64_under_limit(pil_img: Image.Image, max_bytes: int = 3_700_000) -> str:
    """
    Groq base64 image limit is 4MB; keep some buffer.
    We downscale + reduce JPEG quality until under limit.
    """
    img = pil_img.copy()
    quality = 75

    # quick downscale if huge
    max_w = 1600
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))

    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        b = buf.getvalue()
        if len(b) <= max_bytes or quality <= 35:
            return base64.b64encode(b).decode("utf-8")
        quality -= 10
        # if still big, downscale a bit more
        img = img.resize((int(img.width * 0.9), int(img.height * 0.9)))

async def _read_pdf_bytes_from_request(request: Request) -> bytes:
    """
    Works with:
    - multipart/form-data (n8n Binary File)
    - raw application/pdf body
    """
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        # pick the first uploaded file
        for _, v in form.items():
            if hasattr(v, "read"):
                return await v.read()
        raise ValueError("No file found in multipart form")
    # raw body
    return await request.body()

# ---------- endpoint ----------

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/ocr")
async def ocr_endpoint(
    request: Request,
    include_images: bool = False,
    dpi: int = 350,
    start_page: int = 1,
    max_pages: int = 0,  # 0 = all
    lang: str = "ben+eng",  # tesseract language codes (Bengali = ben)
    psm: int = 6,
    oem: int = 1,
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

            cv_img = _preprocess_for_ocr(pil_img)
            text = _ocr_image(cv_img, lang=lang, psm=psm, oem=oem)

            rec: Dict[str, Any] = {"page": pno + 1, "text": text}
            if include_images:
                rec["image_b64_jpeg"] = _jpeg_b64_under_limit(pil_img)

            pages_out.append(rec)

        return {
            "meta": {
                "total_pages": total_pages,
                "start_page": s,
                "end_page": e,
                "dpi": dpi,
                "lang": lang,
                "psm": psm,
                "oem": oem,
                "include_images": include_images,
            },
            "pages": pages_out,
        }

    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=500)