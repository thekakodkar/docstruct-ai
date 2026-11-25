"""Async extract path and confidence-based escalation."""

from __future__ import annotations

import asyncio
import io

from PIL import Image
from pydantic import BaseModel

from docstruct import DocumentClient, MockProvider, RoutingPolicy
from docstruct.providers.base import ProviderCapabilities
from docstruct.providers.mock import MockProvider as MockProv


class Simple(BaseModel):
    vendor: str
    total: float


def _png_bytes() -> bytes:
    img = Image.new("RGB", (24, 24), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_aextract_success():
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    result = asyncio.run(client.aextract(_png_bytes(), schema=Simple))
    assert result.validation.is_valid
    assert result.data.vendor == "ACME Corp"


class LowConfidenceProvider(MockProv):
    name = "low"

    def __init__(self) -> None:
        super().__init__(confidence=0.2, payload={"vendor": "LOW", "total": 1.0})
        self.capabilities = ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=False,
        )


class HighConfidenceProvider(MockProv):
    name = "high"

    def __init__(self) -> None:
        super().__init__(confidence=0.99, payload={"vendor": "HIGH", "total": 99.0})


def test_escalate_on_low_confidence():
    low = LowConfidenceProvider()
    high = HighConfidenceProvider()
    client = DocumentClient(
        providers=[low, high],
        default_routing=RoutingPolicy(
            primary_provider="low",
            fallback_providers=["high"],
            max_retries_per_provider=0,
            escalate_on_low_confidence=0.5,
        ),
    )
    result = asyncio.run(client.aextract(_png_bytes(), schema=Simple))
    assert result.validation.is_valid
    assert result.data.vendor == "HIGH"
    assert result.telemetry.escalations >= 1
    assert "high" in result.telemetry.providers_used


def test_no_escalation_when_confidence_ok():
    low = LowConfidenceProvider()
    client = DocumentClient(
        providers=[low],
        default_routing=RoutingPolicy(
            primary_provider="low",
            max_retries_per_provider=0,
            escalate_on_low_confidence=0.1,
        ),
    )
    result = asyncio.run(client.aextract(_png_bytes(), schema=Simple))
    assert result.data.vendor == "LOW"
