"""Tests for page ingest helpers."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from docstruct.pipeline.ingest import load_pages, pages_from_base64


def _png_bytes(w: int = 64, h: int = 64) -> bytes:
    img = Image.new("RGB", (w, h), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_load_single_image_bytes():
    data = _png_bytes(80, 60)
    pages = load_pages(data)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].width == 80
    assert pages[0].height == 60
    assert pages[0].image_bytes is not None
    assert pages[0].mime_type == "image/png"


def test_pages_from_base64():
    data = _png_bytes(40, 40)
    b64 = base64.b64encode(data).decode("ascii")
    pages = pages_from_base64([b64, b64])
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2


def test_load_from_path(tmp_path):
    data = _png_bytes(50, 50)
    path = tmp_path / "page.png"
    path.write_bytes(data)
    pages = load_pages(path)
    assert len(pages) == 1
    assert pages[0].width == 50
