"""Markdown serialization with optional provenance footnotes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from docstruct.models.result import ExtractionResult


def to_markdown(
    result: ExtractionResult | dict[str, Any] | BaseModel,
    *,
    title: str | None = None,
    include_telemetry: bool = False,
    include_validation: bool = False,
) -> str:
    """
    Render extraction result as provenance-friendly Markdown.

    - Dict/model fields become a definition list / headings
    - Nested lists become Markdown lists or tables when uniform
    - Optional telemetry/validation appendices
    """
    if isinstance(result, ExtractionResult):
        data = result.to_dict(include_telemetry=False)
        ir_md = result.ir.raw_markdown if result.ir else None
        validation = result.validation
        telemetry = result.telemetry
        schema_name = result.schema_name
    elif isinstance(result, BaseModel):
        data = result.model_dump(mode="json")
        ir_md = None
        validation = None
        telemetry = None
        schema_name = None
    else:
        data = dict(result)
        ir_md = None
        validation = None
        telemetry = None
        schema_name = None

    lines: list[str] = []
    doc_title = title or schema_name or "Document"
    lines.append(f"# {doc_title}")
    lines.append("")

    if ir_md:
        lines.append(ir_md.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Structured fields")
        lines.append("")

    lines.extend(_render_value(data, level=2))

    if include_validation and validation is not None:
        lines.append("")
        lines.append("## Validation")
        lines.append("")
        lines.append(f"- **valid**: `{validation.is_valid}`")
        lines.append(f"- **attempts**: `{validation.attempts}`")
        if validation.errors:
            lines.append("- **errors**:")
            for e in validation.errors:
                lines.append(f"  - {e}")

    if include_telemetry and telemetry is not None:
        lines.append("")
        lines.append("## Telemetry")
        lines.append("")
        lines.append(f"- **providers**: {', '.join(telemetry.providers_used) or 'n/a'}")
        lines.append(f"- **latency_ms**: `{telemetry.total_latency_ms:.1f}`")
        lines.append(f"- **pages**: `{telemetry.pages_processed}`")
        lines.append(f"- **retries**: `{telemetry.retries}`")
        lines.append(f"- **escalations**: `{telemetry.escalations}`")

    return "\n".join(lines).rstrip() + "\n"


def _render_value(value: Any, *, level: int = 2) -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, dict):
                lines.append(f"{'#' * min(level, 6)} {key}")
                lines.append("")
                lines.extend(_render_value(val, level=level + 1))
            elif isinstance(val, list):
                lines.append(f"{'#' * min(level, 6)} {key}")
                lines.append("")
                if val and all(isinstance(x, dict) for x in val):
                    # simple table when keys align
                    keys: list[str] = []
                    for row in val:
                        for k in row:
                            if k not in keys:
                                keys.append(k)
                    if keys:
                        lines.append("| " + " | ".join(keys) + " |")
                        lines.append("| " + " | ".join("---" for _ in keys) + " |")
                        for row in val:
                            lines.append(
                                "| "
                                + " | ".join(_cell(row.get(k, "")) for k in keys)
                                + " |"
                            )
                        lines.append("")
                    else:
                        for item in val:
                            lines.append(f"- {item}")
                else:
                    for item in val:
                        lines.append(f"- {item}")
                lines.append("")
            else:
                lines.append(f"- **{key}**: {_cell(val)}")
        if lines and not lines[-1].endswith("\n"):
            lines.append("")
    else:
        lines.append(str(value))
    return lines


def _cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).replace("\n", " ").replace("|", "\\|")
    return s
