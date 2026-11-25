"""Configurable XML serializer with namespaces, attributes, CDATA, and optional XSD."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom

from pydantic import BaseModel

from docstruct.errors import SerializationError
from docstruct.models.result import ExtractionResult


def to_xml(
    result: ExtractionResult | dict[str, Any] | BaseModel,
    *,
    root_tag: str = "Document",
    list_item_tags: dict[str, str] | None = None,
    attribute_fields: set[str] | None = None,
    cdata_fields: set[str] | None = None,
    namespaces: dict[str, str] | None = None,
    xsd_path: str | None = None,
    pretty: bool = True,
) -> str:
    """
    Serialize a validated extraction result to XML.

    Parameters
    ----------
    root_tag:
        Name of the root element.
    list_item_tags:
        Map of list field name → item tag name, e.g. {"lines": "Line"}.
    attribute_fields:
        Fields that should be emitted as XML attributes instead of child elements.
    cdata_fields:
        Fields whose text content should be wrapped in CDATA.
    namespaces:
        Prefix → URI map declared on the root element.
    xsd_path:
        Optional path to an XSD; when provided, the output is validated with lxml.
    """
    if isinstance(result, ExtractionResult):
        data = result.to_dict(include_telemetry=False)
    elif isinstance(result, BaseModel):
        data = result.model_dump(mode="json")
    else:
        data = dict(result)

    list_item_tags = list_item_tags or {}
    attribute_fields = attribute_fields or set()
    cdata_fields = cdata_fields or set()

    # Register namespaces
    if namespaces:
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)

    root_attrib = {}
    if namespaces:
        for prefix, uri in namespaces.items():
            key = f"xmlns:{prefix}" if prefix else "xmlns"
            root_attrib[key] = uri

    root = ET.Element(root_tag, root_attrib)
    _build_element(root, data, list_item_tags, attribute_fields, cdata_fields)

    xml_bytes = ET.tostring(root, encoding="utf-8")
    if pretty:
        reparsed = minidom.parseString(xml_bytes)
        xml_str = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
        # remove extra blank lines minidom sometimes inserts
        lines = [ln for ln in xml_str.splitlines() if ln.strip()]
        xml_str = "\n".join(lines) + "\n"
    else:
        xml_str = xml_bytes.decode("utf-8")

    if xsd_path:
        _validate_xsd(xml_str, xsd_path)

    return xml_str


def _build_element(
    parent: ET.Element,
    data: Any,
    list_item_tags: dict[str, str],
    attribute_fields: set[str],
    cdata_fields: set[str],
) -> None:
    # ElementTree escapes text and attribute values on serialization —
    # do NOT pre-escape or values will be double-escaped.
    if not isinstance(data, dict):
        parent.text = str(data) if data is not None else ""
        return

    for key, value in data.items():
        if key in attribute_fields and not isinstance(value, (dict, list)):
            parent.set(key, str(value) if value is not None else "")
            continue

        if isinstance(value, list):
            item_tag = list_item_tags.get(key, "item")
            container = ET.SubElement(parent, key)
            for item in value:
                child = ET.SubElement(container, item_tag)
                if isinstance(item, dict):
                    _build_element(child, item, list_item_tags, attribute_fields, cdata_fields)
                else:
                    child.text = str(item) if item is not None else ""
            continue

        if isinstance(value, dict):
            child = ET.SubElement(parent, key)
            _build_element(child, value, list_item_tags, attribute_fields, cdata_fields)
            continue

        # scalar
        child = ET.SubElement(parent, key)
        child.text = str(value) if value is not None else ""


def _validate_xsd(xml_str: str, xsd_path: str) -> None:
    try:
        from lxml import etree
    except ImportError as exc:
        raise SerializationError(
            "XSD validation requires the optional [xml] extra: pip install 'docstruct[xml]'"
        ) from exc

    try:
        schema_doc = etree.parse(xsd_path)
        schema = etree.XMLSchema(schema_doc)
        doc = etree.fromstring(xml_str.encode("utf-8"))
        if not schema.validate(doc):
            raise SerializationError(f"XSD validation failed: {schema.error_log}")
    except etree.XMLSyntaxError as exc:
        raise SerializationError(f"Invalid XML produced: {exc}") from exc
