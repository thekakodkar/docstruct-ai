"""Tests for routing, retry, and escalation."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from pydantic import BaseModel

from docstruct import (
    DocumentClient,
    MockProvider,
    ProviderError,
    RoutingPolicy,
    ValidationError,
)
from docstruct.models.ir import DocumentIR


class SimpleSchema(BaseModel):
    vendor: str
    total: float


def _blank_png() -> bytes:
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_primary_provider_success():
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    result = client.extract(_blank_png(), schema=SimpleSchema)
    assert result.validation.is_valid
    assert "mock" in result.telemetry.providers_used


def test_fallback_on_provider_failure():
    failing = MockProvider(fail_times=99, fail_message="primary down")
    failing.name = "primary"
    backup = MockProvider(payload={"vendor": "BACKUP", "total": 99.0})
    backup.name = "backup"

    client = DocumentClient(
        providers=[failing, backup],
        default_routing=RoutingPolicy(
            primary_provider="primary",
            fallback_providers=["backup"],
            max_retries_per_provider=0,
        ),
    )
    result = client.extract(_blank_png(), schema=SimpleSchema)
    assert result.validation.is_valid
    assert result.data.vendor == "BACKUP"
    assert result.telemetry.escalations >= 1


def test_retry_then_succeed():
    """Provider fails once, then succeeds on retry."""
    provider = MockProvider(fail_times=1)
    client = DocumentClient(
        providers=[provider],
        default_routing=RoutingPolicy(
            primary_provider="mock",
            max_retries_per_provider=2,
        ),
    )
    result = client.extract(_blank_png(), schema=SimpleSchema)
    assert result.validation.is_valid
    assert provider._call_count == 2  # 1 fail + 1 success


def test_all_providers_exhausted_raises():
    bad = MockProvider(fail_times=99)
    client = DocumentClient(
        providers=[bad],
        default_routing=RoutingPolicy(
            primary_provider="mock",
            max_retries_per_provider=1,
        ),
    )
    with pytest.raises(ValidationError) as exc:
        client.extract(_blank_png(), schema=SimpleSchema)
    assert exc.value.attempts >= 1


def test_business_rule_failure():
    def always_fail(data, ir: DocumentIR) -> list[str]:
        return ["rule violated"]

    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(
            primary_provider="mock",
            max_retries_per_provider=0,
        ),
    )
    with pytest.raises(ValidationError) as exc:
        client.extract(_blank_png(), schema=SimpleSchema, rules=[always_fail])
    assert "rule violated" in exc.value.errors


def test_schema_validation_catches_bad_types():
    """Mock returns good data; force a schema that cannot match."""

    class Strict(BaseModel):
        vendor: str
        total: str  # string, but mock returns float

    # Use a payload that will fail strict validation
    provider = MockProvider(payload={"vendor": "X", "total": 123.45})
    client = DocumentClient(
        providers=[provider],
        default_routing=RoutingPolicy(
            primary_provider="mock",
            max_retries_per_provider=0,
        ),
    )
    # Pydantic may coerce float→str depending on config; use a clearly wrong shape
    provider2 = MockProvider(payload={"vendor": 999, "total": "not-a-number"})
    client2 = DocumentClient(
        providers=[provider2],
        default_routing=RoutingPolicy(primary_provider="mock", max_retries_per_provider=0),
    )
    with pytest.raises(ValidationError):
        client2.extract(_blank_png(), schema=Strict)
