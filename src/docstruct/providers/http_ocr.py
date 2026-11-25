"""Generic REST / webhook adapter for PaddleOCR-VL, Docling, MinerU, custom OCR services."""

from __future__ import annotations

import time
from typing import Any

import httpx
from pydantic import BaseModel

from docstruct.errors import ProviderError
from docstruct.models.ir import PageInput
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput


class HttpOCRProvider(BaseOCRProvider):
    """
    Flexible HTTP adapter.

    Expects the remote service to accept a JSON body containing base64 images
    (or multipart) and return a JSON object that can be treated as the extraction result.
    """

    name = "http_ocr"

    def __init__(
        self,
        endpoint: str,
        *,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        timeout: float = 180.0,
        name: str = "http_ocr",
        capabilities: ProviderCapabilities | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.method = method.upper()
        self.headers = headers or {}
        self.timeout = timeout
        self.name = name
        self.capabilities = capabilities or ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=True,
            supports_pdf_native=False,
        )

    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        import base64

        start = time.perf_counter()
        images = []
        for p in pages:
            if p.image_bytes:
                b64 = base64.b64encode(p.image_bytes).decode("ascii")
            elif p.image_path:
                with open(p.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            else:
                raise ProviderError("PageInput requires image data", provider=self.name)
            images.append({"page_number": p.page_number, "image_b64": b64})

        body: dict[str, Any] = {
            "images": images,
            "prompt_hint": prompt_hint,
        }
        if schema is not None:
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                body["schema"] = schema.model_json_schema()
            else:
                body["schema"] = schema

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(
                    self.method,
                    self.endpoint,
                    json=body,
                    headers=self.headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"HTTP OCR request failed: {exc}", provider=self.name, cause=exc) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        content = data.get("result", data)

        return ProviderRawOutput(
            content=content,
            latency_ms=latency_ms,
            model=data.get("model"),
            provider_metadata=data.get("metadata", {}),
            bboxes=data.get("bboxes", []),
        )
