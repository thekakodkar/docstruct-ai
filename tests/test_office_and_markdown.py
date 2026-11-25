"""DOCX/PPTX native text, markdown export, and native provider tests."""

from __future__ import annotations

import io
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import BaseModel

from docstruct import DocumentClient, MockProvider, NativeTextProvider, RoutingPolicy
from docstruct.pipeline.ingest import load_native_document, load_pages
from docstruct.serializers.markdown_serializer import to_markdown


def _minimal_docx(paragraphs: list[str]) -> bytes:
    """Build a tiny DOCX (zip) with given paragraphs."""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = Element(f"{{{ns}}}document")
    body = SubElement(document, f"{{{ns}}}body")
    for text in paragraphs:
        p = SubElement(body, f"{{{ns}}}p")
        r = SubElement(p, f"{{{ns}}}r")
        t = SubElement(r, f"{{{ns}}}t")
        t.text = text
    xml = tostring(document, encoding="utf-8", xml_declaration=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def _minimal_pptx(slide_texts: list[list[str]]) -> bytes:
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
""",
        )
        for i, texts in enumerate(slide_texts, start=1):
            sld = Element("sld")
            for text in texts:
                t = SubElement(sld, f"{{{ns_a}}}t")
                t.text = text
            zf.writestr(f"ppt/slides/slide{i}.xml", tostring(sld, encoding="utf-8"))
    return buf.getvalue()


def test_docx_native_text():
    data = _minimal_docx(["Hello Vendor", "Total 100"])
    pages = load_pages(data)
    assert len(pages) >= 1
    assert "Hello Vendor" in pages[0].metadata["native_text"]
    assert "Total 100" in pages[0].metadata["native_text"]

    native = load_native_document(data)
    assert native["format"] == "docx"
    assert "Hello Vendor" in native["markdown"]


def test_pptx_native_text():
    data = _minimal_pptx([["Slide One Title", "Bullet A"], ["Slide Two"]])
    pages = load_pages(data)
    assert len(pages) == 2
    assert "Slide One Title" in pages[0].metadata["native_text"]
    assert "Slide Two" in pages[1].metadata["native_text"]


def test_native_provider_extract():
    data = _minimal_docx(["ACME Invoice", "Amount 50"])
    client = DocumentClient(
        providers=[NativeTextProvider()],
        default_routing=RoutingPolicy(primary_provider="native"),
    )
    # Native provider returns free-form dict; no strict schema
    result = client.extract(data)
    assert result.validation.is_valid
    assert "ACME Invoice" in str(result.data)


def test_markdown_serializer():
    class Inv(BaseModel):
        vendor: str
        total: float
        lines: list[dict]

    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    from PIL import Image

    img = Image.new("RGB", (20, 20), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = client.extract(buf.getvalue(), schema=Inv)
    md = result.to_markdown(title="Invoice", include_telemetry=True, include_validation=True)
    assert md.startswith("# Invoice")
    assert "vendor" in md.lower() or "ACME" in md
    assert "Telemetry" in md
    assert "Validation" in md


def test_extract_native_api():
    data = _minimal_docx(["Line A", "Line B"])
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )
    out = client.extract_native(data)
    assert out["page_count"] >= 1
    assert "Line A" in out["markdown"]
