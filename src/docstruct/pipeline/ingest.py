"""Input loader: PDF, DOCX, PPTX, images -> page images and optional native text."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

from PIL import Image

from docstruct.models.ir import PageInput

# Safety defaults (override via load_pages kwargs)
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_MAX_PAGES = 100
MAX_ZIP_UNCOMPRESSED = 80 * 1024 * 1024  # 80 MB uncompressed office zip


def load_pages(
    source: str | Path | bytes | BinaryIO,
    *,
    dpi: int = 200,
    max_pages: int | None = None,
    prefer_native_text: bool = True,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[PageInput]:
    """
    Convert document input into a list of PageInput records.

    Supports:
    - PDF (optional [pdf] extra) - rasterize pages; attach native text when available
    - DOCX - extract paragraph text (stdlib zip+xml); optional page images not generated
    - PPTX - extract slide text (stdlib zip+xml)
    - PNG / JPEG / WebP / TIFF images
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

    if max_file_bytes and len(data) > max_file_bytes:
        raise ValueError(
            f"File too large ({len(data)} bytes). Max allowed is {max_file_bytes} bytes "
            f"(pass max_file_bytes=... to raise the limit)."
        )

    if max_pages is None:
        max_pages = DEFAULT_MAX_PAGES

    if suffix == ".pdf":
        return _pdf_to_pages(
            data, dpi=dpi, max_pages=max_pages, source_name=source_name, prefer_native_text=prefer_native_text
        )
    if suffix in {".docx", ".doc"}:
        return _docx_to_pages(data, max_pages=max_pages, source_name=source_name)
    if suffix in {".pptx", ".ppt"}:
        return _pptx_to_pages(data, max_pages=max_pages, source_name=source_name)

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


def load_native_document(
    source: str | Path | bytes | BinaryIO,
    *,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """
    Load text-first representation without requiring vision models.

    Returns dict with keys: source_name, format, pages (list of {page_number, text}), markdown.
    Ideal for digital PDFs, DOCX, and PPTX when OCR is unnecessary.
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
        pages = _pdf_native_text(data, max_pages=max_pages)
        fmt = "pdf"
    elif suffix in {".docx", ".doc"}:
        pages = [
            {"page_number": p.page_number, "text": (p.metadata or {}).get("native_text", "")}
            for p in _docx_to_pages(data, max_pages=max_pages, source_name=source_name)
        ]
        fmt = "docx"
    elif suffix in {".pptx", ".ppt"}:
        pages = [
            {"page_number": p.page_number, "text": (p.metadata or {}).get("native_text", "")}
            for p in _pptx_to_pages(data, max_pages=max_pages, source_name=source_name)
        ]
        fmt = "pptx"
    else:
        raise ValueError(f"Native text extraction not supported for {suffix or 'unknown'} format")

    md_parts = []
    for p in pages:
        md_parts.append(f"## Page {p['page_number']}\n\n{p['text'].strip()}\n")
    return {
        "source_name": source_name,
        "format": fmt,
        "page_count": len(pages),
        "pages": pages,
        "markdown": "\n".join(md_parts).strip() + "\n",
    }


def _pdf_to_pages(
    data: bytes,
    *,
    dpi: int,
    max_pages: int | None,
    source_name: str,
    prefer_native_text: bool = True,
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
        native = page.get_text("text").strip() if prefer_native_text else ""
        pages.append(
            PageInput(
                page_number=i + 1,
                image_bytes=img_bytes,
                width=pix.width,
                height=pix.height,
                mime_type="image/png",
                metadata={"native_text": native, "source_name": source_name} if native else {"source_name": source_name},
            )
        )
    doc.close()
    return pages


def _pdf_native_text(data: bytes, *, max_pages: int | None) -> list[dict[str, Any]]:
    try:
        import fitz
    except ImportError as exc:
        raise ImportError(
            "PDF support requires the optional [pdf] extra: pip install 'docstruct[pdf]'"
        ) from exc

    doc = fitz.open(stream=data, filetype="pdf")
    limit = max_pages or doc.page_count
    out = []
    for i in range(min(doc.page_count, limit)):
        page = doc.load_page(i)
        out.append({"page_number": i + 1, "text": page.get_text("text")})
    doc.close()
    return out



def _assert_safe_zip(zf: zipfile.ZipFile) -> None:
    total = 0
    for info in zf.infolist():
        total += info.file_size
        if total > MAX_ZIP_UNCOMPRESSED:
            raise ValueError(
                f"Office archive uncompressed size exceeds safety limit ({MAX_ZIP_UNCOMPRESSED} bytes)"
            )

def _docx_to_pages(
    data: bytes,
    *,
    max_pages: int | None,
    source_name: str,
) -> list[PageInput]:
    """Extract DOCX text via stdlib zip + XML (no python-docx required)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid DOCX file") from exc
    _assert_safe_zip(zf)

    try:
        xml_bytes = zf.read("word/document.xml")
    except KeyError as exc:
        raise ValueError("DOCX missing word/document.xml") from exc

    # WordprocessingML namespace
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for p in root.findall(".//w:p", ns):
        parts = [t.text or "" for t in p.findall(".//w:t", ns)]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)

    # Split into pseudo-pages by form feed or every ~40 paragraphs
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in paragraphs:
        if line == "\f" or line == "\x0c":
            if current:
                chunks.append(current)
                current = []
            continue
        current.append(line)
        if max_pages and len(chunks) >= max_pages:
            break
        if len(current) >= 40:
            chunks.append(current)
            current = []
    if current and (not max_pages or len(chunks) < max_pages):
        chunks.append(current)
    if not chunks:
        chunks = [[]]

    pages: list[PageInput] = []
    for i, chunk in enumerate(chunks[: max_pages or len(chunks)]):
        text = "\n".join(chunk)
        pages.append(
            PageInput(
                page_number=i + 1,
                image_bytes=None,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                metadata={"native_text": text, "source_name": source_name, "format": "docx"},
            )
        )
    return pages


def _pptx_to_pages(
    data: bytes,
    *,
    max_pages: int | None,
    source_name: str,
) -> list[PageInput]:
    """Extract PPTX slide text via stdlib zip + XML."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid PPTX file") from exc
    _assert_safe_zip(zf)

    slide_names = sorted(
        n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")
    )
    if max_pages:
        slide_names = slide_names[:max_pages]

    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    pages: list[PageInput] = []
    for i, name in enumerate(slide_names):
        root = ET.fromstring(zf.read(name))
        texts = [t.text or "" for t in root.findall(".//a:t", ns) if t.text]
        text = "\n".join(texts)
        pages.append(
            PageInput(
                page_number=i + 1,
                image_bytes=None,
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                metadata={"native_text": text, "source_name": source_name, "format": "pptx"},
            )
        )
    if not pages:
        pages.append(
            PageInput(
                page_number=1,
                metadata={"native_text": "", "source_name": source_name, "format": "pptx"},
            )
        )
    return pages


def _guess_suffix(data: bytes) -> str:
    if data[:4] == b"%PDF":
        return ".pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:2] == b"PK":
        # zip-based office
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            names = set(zf.namelist())
            if "word/document.xml" in names:
                return ".docx"
            if any(n.startswith("ppt/slides/") for n in names):
                return ".pptx"
        except zipfile.BadZipFile:
            pass
        return ".zip"
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
