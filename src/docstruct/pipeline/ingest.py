"""Input loader: file path, bytes, base64, multi-page PDF → page images."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import BinaryIO

from PIL import Image

from docstruct.models.ir import PageInput


def load_pages(
    source: str | Path | bytes | BinaryIO,
    *,
    dpi: int = 200,
    max_pages: int | None = None,
) -> list[PageInput]:
    """
    Convert almost any document input into a list of PageInput images.

    Supports:
    - PDF (requires optional [pdf] extra)
    - PNG / JPEG / WebP / TIFF images
    - raw bytes or file-like objects
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        data = path.read_bytes()
        source_name = path.name
    elif isinstance(source, bytes):
        data = source
        source_name = "bytes"
        suffix = _guess_suffix(data)
    else:
        data = source.read()
        source_name = getattr(source, "name", "stream")
        suffix = _guess_suffix(data)

    if suffix == ".pdf":
        return _pdf_to_pages(data, dpi=dpi, max_pages=max_pages, source_name=source_name)

    # Single image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return [
        PageInput(
            page_number=1,
            image_bytes=buf.getvalue(),
            width=img.width,
            height=img.height,
            mime_type="image/png",
        )
    ]


def _pdf_to_pages(
    data: bytes,
    *,
    dpi: int,
    max_pages: int | None,
    source_name: str,
) -> list[PageInput]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError(
            "PDF support requires the optional [pdf] extra: pip install 'docstruct[pdf]'"
        ) from exc

    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[PageInput] = []
    limit = max_pages or doc.page_count

    for i in range(min(doc.page_count, limit)):
        page = doc.load_page(i)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        pages.append(
            PageInput(
                page_number=i + 1,
                image_bytes=img_bytes,
                width=pix.width,
                height=pix.height,
                mime_type="image/png",
            )
        )
    doc.close()
    return pages


def _guess_suffix(data: bytes) -> str:
    if data[:4] == b"%PDF":
        return ".pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    return ".bin"


def pages_from_base64(images_b64: list[str]) -> list[PageInput]:
    """Convenience helper for pre-encoded page images."""
    pages = []
    for i, b64 in enumerate(images_b64, start=1):
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        pages.append(
            PageInput(
                page_number=i,
                image_bytes=raw,
                width=img.width,
                height=img.height,
            )
        )
    return pages
