"""Native text provider for digital PDFs, DOCX, and PPTX (no vision model)."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from docstruct.errors import ProviderError
from docstruct.models.ir import PageInput
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput


class NativeTextProvider(BaseOCRProvider):
    """
    Zero-model provider that structures already-extracted native text.

    Use for digital PDFs/DOCX/PPTX when OCR is unnecessary. When a schema is
    provided, returns a simple {\"text\": ..., \"pages\": [...]} payload that
    downstream rules or a secondary VLM pass can refine.
    """

    name = "native"

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=False,
            supports_pdf_native=True,
            max_pages_per_call=None,
        )

    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        start = time.perf_counter()
        page_payloads = []
        texts: list[str] = []
        for p in pages:
            native = ""
            if p.metadata:
                native = str(p.metadata.get("native_text") or "")
            if not native and not p.image_bytes:
                # still allow empty
                pass
            texts.append(native)
            page_payloads.append({"page_number": p.page_number, "text": native})

        if not any(t.strip() for t in texts):
            raise ProviderError(
                "No native text available on pages (scan-only document?). "
                "Use an OCR/VLM provider instead.",
                provider=self.name,
            )

        full_text = "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['text']}" for p in page_payloads
        )
        content: dict[str, Any] = {
            "text": full_text,
            "pages": page_payloads,
            "page_count": len(page_payloads),
        }
        # Best-effort: if schema looks like a simple text container, leave as-is.
        # Real structured mapping still needs a VLM or custom rules.
        latency_ms = (time.perf_counter() - start) * 1000
        return ProviderRawOutput(
            content=content,
            pages=page_payloads,
            confidence=0.9 if any(t.strip() for t in texts) else 0.2,
            latency_ms=latency_ms,
            model="native-text",
            provider_metadata={"mode": "native", "prompt_hint": prompt_hint},
        )
