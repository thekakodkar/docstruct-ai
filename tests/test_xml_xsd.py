"""XSD validation path for XML serializer."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from docstruct.errors import SerializationError
from docstruct.models.ir import DocumentIR
from docstruct.models.result import ExtractionResult, Telemetry, ValidationReport
from docstruct.serializers.xml_serializer import to_xml


class SimpleDoc(BaseModel):
    vendor: str
    total: float


def _result(data: BaseModel) -> ExtractionResult:
    return ExtractionResult(
        data=data,
        ir=DocumentIR(source_name="t.pdf", page_count=1),
        validation=ValidationReport(is_valid=True, attempts=1),
        telemetry=Telemetry(),
    )


XSD_OK = """\
<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Invoice">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="vendor" type="xs:string"/>
        <xs:element name="total" type="xs:decimal"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

XSD_STRICT_EXTRA = """\
<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Invoice">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="vendor" type="xs:string"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


def test_xsd_validation_passes(tmp_path: Path):
    pytest.importorskip("lxml")
    xsd_path = tmp_path / "ok.xsd"
    xsd_path.write_text(XSD_OK, encoding="utf-8")

    xml = to_xml(
        _result(SimpleDoc(vendor="ACME", total=10.5)),
        root_tag="Invoice",
        xsd_path=str(xsd_path),
    )
    assert "<vendor>ACME</vendor>" in xml
    assert "<total>10.5</total>" in xml


def test_xsd_validation_fails(tmp_path: Path):
    pytest.importorskip("lxml")
    xsd_path = tmp_path / "strict.xsd"
    xsd_path.write_text(XSD_STRICT_EXTRA, encoding="utf-8")

    # Schema only allows vendor; total should make validation fail
    with pytest.raises(SerializationError, match="XSD validation failed"):
        to_xml(
            _result(SimpleDoc(vendor="ACME", total=10.5)),
            root_tag="Invoice",
            xsd_path=str(xsd_path),
        )


def test_xsd_without_lxml_raises_clear_error(tmp_path: Path, monkeypatch):
    xsd_path = tmp_path / "ok.xsd"
    xsd_path.write_text(XSD_OK, encoding="utf-8")

    import docstruct.serializers.xml_serializer as mod

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "lxml" or name.startswith("lxml."):
            raise ImportError("No module named lxml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(SerializationError, match=r"docstruct\[xml\]"):
        to_xml(
            _result(SimpleDoc(vendor="X", total=1.0)),
            root_tag="Invoice",
            xsd_path=str(xsd_path),
        )
