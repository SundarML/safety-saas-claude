# core/logo_utils.py
"""
Shared helpers for embedding org logos in PDF and Excel exports.
Works with both local storage and S3 (reads via Django's storage API).
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional


def _read_logo_bytes(org) -> Optional[bytes]:
    """Read raw logo bytes from storage.  Returns None if no logo or any error."""
    if not org:
        return None
    logo = getattr(org, "logo", None)
    if not logo or not logo.name:
        return None
    try:
        with logo.open("rb") as f:
            return f.read()
    except Exception:
        return None


def get_logo_for_pdf(org, max_width_pt: float, max_height_pt: float):
    """
    Return a ReportLab Image flowable scaled to fit within max_width_pt × max_height_pt,
    preserving aspect ratio.  Returns None when no logo is available.

    Usage:
        logo_img = get_logo_for_pdf(org, 6*cm, 1.5*cm)
        if logo_img:
            story.append(logo_img)
    """
    logo_bytes = _read_logo_bytes(org)
    if not logo_bytes:
        return None
    try:
        from PIL import Image as PILImage
        from reportlab.platypus import Image as RLImage

        pil = PILImage.open(BytesIO(logo_bytes))
        orig_w, orig_h = pil.size
        ratio = min(max_width_pt / orig_w, max_height_pt / orig_h)
        return RLImage(BytesIO(logo_bytes), width=orig_w * ratio, height=orig_h * ratio)
    except Exception:
        return None


def get_logo_for_excel(org):
    """
    Return an openpyxl Image object ready to be anchored in a worksheet.
    Returns None when no logo is available.

    Usage:
        xl_img = get_logo_for_excel(org)
        if xl_img:
            xl_img.anchor = "A1"
            ws.add_image(xl_img)
    """
    logo_bytes = _read_logo_bytes(org)
    if not logo_bytes:
        return None
    try:
        from openpyxl.drawing.image import Image as XLImage
        from PIL import Image as PILImage

        # Scale down to a standard header height (≈ 48px / 36pt) preserving aspect ratio
        pil = PILImage.open(BytesIO(logo_bytes))
        orig_w, orig_h = pil.size
        target_h = 48          # pixels
        scale = target_h / orig_h
        new_w = int(orig_w * scale)
        new_h = target_h

        pil_resized = pil.resize((new_w, new_h), PILImage.LANCZOS)

        # openpyxl needs a file-like object; save resized PIL image as PNG into BytesIO
        buf = BytesIO()
        pil_resized.save(buf, format="PNG")
        buf.seek(0)

        xl_img = XLImage(buf)
        xl_img.width = new_w
        xl_img.height = new_h
        return xl_img
    except Exception:
        return None
