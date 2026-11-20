"""Opening uploaded images and PDFs without letting one file take the server down.

A small file can unpack to gigabytes: a 12 MB PNG of one colour can be a gigapixel, and a PDF can declare a page
hundreds of inches wide. Both are checked before anything is decoded or drawn, and big phone photos are decoded at
a fraction of their size instead of in full.
"""
from __future__ import annotations

import io

MAX_PIXELS = 40_000_000  # about 8000 × 5000: more than any phone photo or screenshot after the JPEG shrink below
PDF_MAX_SIDE = 2400      # pixels: a page is never drawn bigger than this, whatever size it claims


def open_image(data: bytes, max_side: int):
    """An uploaded image as an RGB PIL image, upright (phone photos carry their rotation in EXIF), decoded at no more
    than about ``max_side`` when it is a JPEG. Raises ValueError for anything unreadable or too big to decode."""
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))  # reads the header only; PIL itself refuses a gross "decompression bomb"
        longest = max(img.size)
        if longest > max_side:  # JPEG: decode at 1/2, 1/4 or 1/8 scale, never below max_side (other formats ignore it)
            img.draft("RGB", (max(1, img.width * max_side // longest), max(1, img.height * max_side // longest)))
        if img.width * img.height > MAX_PIXELS:
            raise ValueError(f"image too large to open ({img.width} × {img.height})")
        return ImageOps.exif_transpose(img).convert("RGB")
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - PIL raises many types for a bad file
        raise ValueError("not a readable image") from exc


def square_jpeg(data: bytes, side: int) -> bytes:
    """A profile photo: the middle square of the picture (a little above centre, where faces are), ``side`` pixels,
    as a fresh JPEG. Nothing of the original file is kept, so a phone photo's EXIF (which can say where it was
    taken) is gone. Raises ValueError."""
    from PIL import Image, ImageOps

    img = ImageOps.fit(open_image(data, side * 2), (side, side), Image.LANCZOS, centering=(0.5, 0.4))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def pdf_page_jpeg(page, dpi: int) -> bytes:
    """One PDF page drawn as a JPEG at ``dpi``, or smaller when the page claims a size that would be enormous."""
    import pymupdf

    longest = max(page.rect.width, page.rect.height, 1.0)  # in points (1/72 inch)
    zoom = min(dpi / 72, PDF_MAX_SIDE / longest)
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("jpeg")
