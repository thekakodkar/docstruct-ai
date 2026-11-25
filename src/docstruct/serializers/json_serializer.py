"""Deterministic JSON / NDJSON serialization."""

from __future__ import annotations

import json
from typing import Any, Iterable

from pydantic import BaseModel

from docstruct.models.result import ExtractionResult


def _default(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def to_dict(
    result: ExtractionResult | dict[str, Any] | BaseModel,
    *,
    include_telemetry: bool = False,
) -> dict[str, Any]:
    if isinstance(result, ExtractionResult):
        return result.to_dict(include_telemetry=include_telemetry)
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return dict(result)


def to_json(
    result: ExtractionResult | dict[str, Any] | BaseModel,
    *,
    indent: int | None = 2,
    include_telemetry: bool = False,
    ensure_ascii: bool = False,
) -> str:
    payload = to_dict(result, include_telemetry=include_telemetry)
    return json.dumps(
        payload,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=True,
        default=_default,
    )


def to_ndjson(
    results: Iterable[ExtractionResult | dict[str, Any] | BaseModel],
    *,
    include_telemetry: bool = False,
) -> str:
    """Return newline-delimited JSON (one object per line, terminated by \\n)."""
    lines = []
    for r in results:
        lines.append(to_json(r, indent=None, include_telemetry=include_telemetry))
    return "\n".join(lines) + ("\n" if lines else "")
