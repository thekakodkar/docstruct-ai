"""Tests for JSON, NDJSON, and XML serializers."""

from __future__ import annotations

import json
import re

import pytest
from pydantic import BaseModel

from docstruct.models.ir import DocumentIR
from docstruct.models.result import ExtractionResult, Telemetry, ValidationReport
from docstruct.serializers import to_dict, to_json, to_ndjson, to_xml
from docstruct.serializers.xml_serializer import SerializationError


class LineItem(BaseModel):
    description: str
    qty: float
    amount: float


class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str = "USD"
    lines: list[LineItem] = []
    notes: str | None = None


def _make_result(data: BaseModel | dict) -> ExtractionResult:
    return ExtractionResult(
        data=data,
        ir=DocumentIR(source_name="test.pdf", page_count=1),
        validation=ValidationReport(is_valid=True, attempts=1),
        telemetry=Telemetry(total_latency_ms=10.0, pages_processed=1),
        schema_name="Invoice",
    )


def test_to_json_deterministic_key_order():
    inv = Invoice(
        vendor="ACME",
        invoice_number="INV-1",
        total=100.0,
        lines=[LineItem(description="A", qty=1, amount=100.0)],
    )
    result = _make_result(inv)
    js = to_json(result, indent=None)
    # sort_keys=True → alphabetical
    assert js.index("currency") < js.index("invoice_number")
    assert js.index("invoice_number") < js.index("total")
    assert js.index("total") < js.index("vendor")


def test_to_json_with_telemetry():
    inv = Invoice(vendor="X", invoice_number="1", total=1.0)
    result = _make_result(inv)
    js = to_json(result, include_telemetry=True)
    data = json.loads(js)
    assert "_meta" in data
    assert data["_meta"]["validation"]["is_valid"] is True
    assert data["_meta"]["schema_name"] == "Invoice"


def test_to_ndjson_multiple():
    r1 = _make_result(Invoice(vendor="A", invoice_number="1", total=10.0))
    r2 = _make_result(Invoice(vendor="B", invoice_number="2", total=20.0))
    nd = to_ndjson([r1, r2])
    lines = [ln for ln in nd.strip().split("\n") if ln]
    assert len(lines) == 2
    assert json.loads(lines[0])["vendor"] == "A"
    assert json.loads(lines[1])["vendor"] == "B"
    assert nd.endswith("\n")


def test_xml_basic():
    inv = Invoice(
        vendor="ACME Corp",
        invoice_number="INV-100",
        total=250.5,
        lines=[
            LineItem(description="Widget", qty=2, amount=200.0),
            LineItem(description="Fee", qty=1, amount=50.5),
        ],
    )
    result = _make_result(inv)
    xml = to_xml(result, root_tag="Invoice", list_item_tags={"lines": "Line"})
    assert "<Invoice>" in xml
    assert "<vendor>ACME Corp</vendor>" in xml
    assert "<Line>" in xml
    assert "<description>Widget</description>" in xml
    assert xml.count("<Line>") == 2


def test_xml_attributes():
    inv = Invoice(vendor="X", invoice_number="INV-9", total=9.0, currency="EUR")
    result = _make_result(inv)
    xml = to_xml(
        result,
        root_tag="Invoice",
        attribute_fields={"currency", "invoice_number"},
    )
    assert 'currency="EUR"' in xml or "currency=\"EUR\"" in xml
    assert 'invoice_number="INV-9"' in xml or "invoice_number=\"INV-9\"" in xml
    # attributes should not also appear as child elements
    assert "<currency>" not in xml
    assert "<invoice_number>" not in xml


def test_xml_escaping():
    inv = Invoice(
        vendor='A & B <Corp> "Ltd"',
        invoice_number="1",
        total=1.0,
        notes="Line1\nLine2",
    )
    result = _make_result(inv)
    xml = to_xml(result, root_tag="Doc")
    assert "&amp;" in xml
    assert "&lt;" in xml
    assert "&gt;" in xml
    assert "&quot;" in xml


def test_xml_namespaces():
    inv = Invoice(vendor="X", invoice_number="1", total=1.0)
    result = _make_result(inv)
    xml = to_xml(
        result,
        root_tag="inv:Invoice",
        namespaces={"inv": "http://example.com/invoice/v1"},
    )
    assert "xmlns:inv" in xml or "http://example.com/invoice/v1" in xml


def test_to_dict_from_pydantic():
    inv = Invoice(vendor="Z", invoice_number="Z1", total=0.0)
    d = to_dict(inv)
    assert d["vendor"] == "Z"
    assert isinstance(d, dict)
