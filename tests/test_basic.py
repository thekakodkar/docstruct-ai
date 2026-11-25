"""Basic smoke tests for docstruct."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from docstruct import (
    DocumentClient,
    MockProvider,
    RoutingPolicy,
    ValidationError,
)
from docstruct.serializers import to_json, to_ndjson, to_xml


class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float


class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str = "USD"
    lines: list[LineItem] = []


def test_mock_extract_json():
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    # Use a tiny PNG-like bytes (will be treated as image)
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = client.extract(buf.getvalue(), schema=Invoice)
    assert result.validation.is_valid
    assert result.data.vendor == "ACME Corp"
    assert result.data.total == 1250.0

    js = result.to_json()
    parsed = json.loads(js)
    assert parsed["invoice_number"] == "INV-1001"


def test_xml_serializer():
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    from PIL import Image
    import io

    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = client.extract(buf.getvalue(), schema=Invoice)
    xml = result.to_xml(root_tag="Invoice", list_item_tags={"lines": "Line"})
    assert "<Invoice>" in xml
    assert "<vendor>ACME Corp</vendor>" in xml
    assert "Line" in xml


def test_ndjson():
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    from PIL import Image
    import io

    img = Image.new("RGB", (40, 40), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r1 = client.extract(buf.getvalue(), schema=Invoice)
    r2 = client.extract(buf.getvalue(), schema=Invoice)
    nd = to_ndjson([r1, r2])
    lines = [ln for ln in nd.strip().split("\n") if ln]
    assert len(lines) == 2
    assert json.loads(lines[0])["vendor"] == "ACME Corp"


def test_validation_failure_and_retry():
    def bad_rule(data, ir):
        return ["forced failure"]

    client = DocumentClient(
        providers=[MockProvider(fail_times=0)],
        default_routing=RoutingPolicy(
            primary_provider="mock",
            max_retries_per_provider=0,
        ),
    )
    from PIL import Image
    import io

    img = Image.new("RGB", (30, 30), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    with pytest.raises(ValidationError) as exc:
        client.extract(buf.getvalue(), schema=Invoice, rules=[bad_rule])
    assert "forced failure" in str(exc.value.errors)
