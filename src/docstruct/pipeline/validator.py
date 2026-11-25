"""Schema validation + custom rule hooks + selective repair loop."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError as PydanticValidationError

from docstruct.errors import ValidationError
from docstruct.models.ir import DocumentIR
from docstruct.models.result import ValidationReport
from docstruct.models.schema import normalize_schema


def validate_and_parse(
    raw: dict[str, Any] | str,
    schema: type[BaseModel] | dict[str, Any] | None,
    rules: list[Callable[[BaseModel | dict[str, Any], DocumentIR], list[str]]] | None = None,
    ir: DocumentIR | None = None,
) -> tuple[BaseModel | dict[str, Any], ValidationReport]:
    """
    Parse raw provider output against the schema and run business rules.
    Returns (parsed_data, ValidationReport).
    """
    model_cls = normalize_schema(schema)
    errors: list[str] = []
    parsed: BaseModel | dict[str, Any]

    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {}, ValidationReport(is_valid=False, errors=[f"Invalid JSON: {exc}"], attempts=1)

    if model_cls is not None:
        try:
            parsed = model_cls.model_validate(raw)
        except PydanticValidationError as exc:
            errors.extend([e["msg"] for e in exc.errors()])
            return raw if isinstance(raw, dict) else {}, ValidationReport(
                is_valid=False, errors=errors, attempts=1
            )
    else:
        parsed = raw if isinstance(raw, dict) else {"value": raw}

    # Custom business rules
    rule_errors: list[str] = []
    if rules and ir is not None:
        for rule in rules:
            try:
                msgs = rule(parsed, ir)
                if msgs:
                    rule_errors.extend(msgs)
            except Exception as exc:  # noqa: BLE001
                rule_errors.append(f"Rule raised: {exc}")

    all_errors = errors + rule_errors
    return parsed, ValidationReport(
        is_valid=len(all_errors) == 0,
        errors=all_errors,
        attempts=1,
        rules_failed=rule_errors,
    )


def build_repair_prompt(errors: list[str], previous: dict[str, Any] | str) -> str:
    """Create a targeted repair instruction for the next provider call."""
    err_text = "\n".join(f"- {e}" for e in errors)
    return (
        "The previous extraction failed validation with these errors:\n"
        f"{err_text}\n\n"
        "Previous output (for reference only):\n"
        f"{previous}\n\n"
        "Please correct the fields and return a complete, valid JSON object."
    )
