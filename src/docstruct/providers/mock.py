"""Deterministic MockProvider for unit and integration tests."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from docstruct.models.ir import PageInput
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput


class MockProvider(BaseOCRProvider):
    """
    Deterministic test double.

    Returns a fixed payload (or a callable-generated one) so tests can
    exercise routing, validation, retry, and serialization without
    real model calls.
    """

    name = "mock"

    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        payload_factory: Any = None,
        confidence: float = 0.95,
        latency_ms: float = 12.0,
        fail_times: int = 0,
        fail_message: str = "mock failure",
    ) -> None:
        self.capabilities = ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=True,
            supports_pdf_native=False,
            max_pages_per_call=50,
        )
        self._payload = payload or {
            "vendor": "ACME Corp",
            "invoice_number": "INV-1001",
            "total": 1250.00,
            "currency": "USD",
            "lines": [
                {"description": "Widget A", "qty": 2, "unit_price": 500.0, "amount": 1000.0},
                {"description": "Service B", "qty": 1, "unit_price": 250.0, "amount": 250.0},
            ],
        }
        self._payload_factory = payload_factory
        self._confidence = confidence
        self._latency_ms = latency_ms
        self._fail_times = fail_times
        self._fail_message = fail_message
        self._call_count = 0

    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        self._call_count += 1
        if self._call_count <= self._fail_times:
            from docstruct.errors import ProviderError

            raise ProviderError(self._fail_message, provider=self.name)

        # Simulate work
        time.sleep(self._latency_ms / 1000.0)

        content = self._payload_factory() if callable(self._payload_factory) else self._payload

        return ProviderRawOutput(
            content=content,
            pages=[{"page_number": p.page_number, "blocks": []} for p in pages],
            confidence=self._confidence,
            latency_ms=self._latency_ms,
            model="mock-v1",
            provider_metadata={"call_count": self._call_count, "prompt_hint": prompt_hint},
            bboxes=[],
        )
