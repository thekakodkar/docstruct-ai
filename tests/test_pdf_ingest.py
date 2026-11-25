"""PDF ingest tests (skip multi-page render when PyMuPDF is absent)."""

from __future__ import annotations

import io

import pytest

from docstruct.pipeline.ingest import load_pages

# Minimal valid one-page PDF (blank page)
MINIMAL_PDF = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 0 >>
stream
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
284
%%EOF
"""


def test_pdf_without_extra_raises_import_error():
    """When PyMuPDF is not installed, PDF input must raise a clear ImportError."""
    pytest.importorskip  # keep pytest happy in collection
    try:
        import fitz  # noqa: F401
        pytest.skip("PyMuPDF is installed; skip the missing-extra path")
    except ImportError:
        pass

    with pytest.raises(ImportError, match=r"docstruct\[pdf\]"):
        load_pages(MINIMAL_PDF)


def test_pdf_multi_page_with_pymupdf():
    fitz = pytest.importorskip("fitz")

    # Build a 3-page PDF in memory
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=200, height=280)
        page.insert_text((20, 40), f"Page {i + 1}")
    pdf_bytes = doc.tobytes()
    doc.close()

    pages = load_pages(pdf_bytes, dpi=72)
    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert pages[2].page_number == 3
    assert pages[0].image_bytes is not None
    assert pages[0].width is not None and pages[0].width > 0

    # max_pages limit
    limited = load_pages(pdf_bytes, dpi=72, max_pages=2)
    assert len(limited) == 2


def test_pdf_from_path(tmp_path):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page(width=100, height=100)
    path = tmp_path / "one.pdf"
    doc.save(path)
    doc.close()

    pages = load_pages(path, dpi=72)
    assert len(pages) == 1
    assert pages[0].mime_type == "image/png"
