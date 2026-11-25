"""Extraction result, telemetry, and validation models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from docstruct.models.ir import DocumentIR


class ProvenanceRecord(BaseModel):
    """Provenance for a single extraction attempt or block."""

    provider: str
    model: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    confidence: float | None = None
    latency_ms: float | None = None
    estimated_cost_usd: float | None = None
    bboxes: list[dict[str, Any]] = Field(default_factory=list)


class Telemetry(BaseModel):
    """Run-level cost, latency, and routing telemetry."""

    total_latency_ms: float = 0.0
    total_estimated_cost_usd: float = 0.0
    providers_used: list[str] = Field(default_factory=list)
    pages_processed: int = 0
    retries: int = 0
    escalations: int = 0
    records: list[ProvenanceRecord] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Explicit validation audit trail."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    attempts: int = 0
    rules_failed: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Final validated extraction payload with full audit trail."""

    data: dict[str, Any] | BaseModel
    ir: DocumentIR | None = None
    validation: ValidationReport
    telemetry: Telemetry = Field(default_factory=Telemetry)
    schema_name: str | None = None

    def to_dict(self, *, include_telemetry: bool = False) -> dict[str, Any]:
        """Return a plain dict suitable for JSON serialization."""
        if isinstance(self.data, BaseModel):
            payload = self.data.model_dump(mode="json")
        else:
            payload = dict(self.data)

        if include_telemetry:
            payload = {
                **payload,
                "_meta": {
                    "validation": self.validation.model_dump(),
                    "telemetry": self.telemetry.model_dump(),
                    "schema_name": self.schema_name,
                },
            }
        return payload

    def to_json(self, *, indent: int | None = 2, include_telemetry: bool = False) -> str:
        """Serialize to a deterministic JSON string."""
        from docstruct.serializers.json_serializer import to_json

        return to_json(self, indent=indent, include_telemetry=include_telemetry)

    def to_markdown(
        self,
        *,
        title: str | None = None,
        include_telemetry: bool = False,
        include_validation: bool = False,
    ) -> str:
        """Serialize to Markdown."""
        from docstruct.serializers.markdown_serializer import to_markdown

        return to_markdown(
            self,
            title=title,
            include_telemetry=include_telemetry,
            include_validation=include_validation,
        )

    def to_xml(
        self,
        *,
        root_tag: str = "Document",
        list_item_tags: dict[str, str] | None = None,
        attribute_fields: set[str] | None = None,
        cdata_fields: set[str] | None = None,
        namespaces: dict[str, str] | None = None,
        xsd_path: str | None = None,
        pretty: bool = True,
    ) -> str:
        """Serialize to configurable XML."""
        from docstruct.serializers.xml_serializer import to_xml

        return to_xml(
            self,
            root_tag=root_tag,
            list_item_tags=list_item_tags,
            attribute_fields=attribute_fields,
            cdata_fields=cdata_fields,
            namespaces=namespaces,
            xsd_path=xsd_path,
            pretty=pretty,
        )
