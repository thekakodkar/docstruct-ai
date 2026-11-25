"""HttpOCRProvider tests with a mocked HTTP transport."""

from __future__ import annotations

import asyncio
import io
import json

import httpx
import pytest
from PIL import Image
from pydantic import BaseModel

from docstruct.errors import ProviderError
from docstruct.models.ir import PageInput
from docstruct.providers.http_ocr import HttpOCRProvider


class Tiny(BaseModel):
    vendor: str
    total: float


def _page() -> PageInput:
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return PageInput(page_number=1, image_bytes=buf.getvalue(), width=32, height=32)


def test_http_ocr_success(monkeypatch):
    payload = {"result": {"vendor": "HTTP Corp", "total": 42.0}, "model": "demo-ocr"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.content.decode("utf-8"))
        assert "images" in body
        assert body["images"][0]["page_number"] == 1
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    provider = HttpOCRProvider(endpoint="http://ocr.test/extract", name="http_ocr")

    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    out = asyncio.run(provider.extract_pages([_page()], schema=Tiny))
    assert out.content["vendor"] == "HTTP Corp"
    assert out.content["total"] == 42.0
    assert out.model == "demo-ocr"
    assert out.latency_ms is not None and out.latency_ms >= 0


def test_http_ocr_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    transport = httpx.MockTransport(handler)
    provider = HttpOCRProvider(endpoint="http://ocr.test/extract")

    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(ProviderError, match="HTTP OCR request failed"):
        asyncio.run(provider.extract_pages([_page()]))


def test_http_ocr_missing_image_raises():
    provider = HttpOCRProvider(endpoint="http://ocr.test/extract")
    bad = PageInput(page_number=1)
    with pytest.raises(ProviderError, match="image"):
        asyncio.run(provider.extract_pages([bad]))
