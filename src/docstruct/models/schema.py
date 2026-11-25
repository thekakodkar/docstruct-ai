"""Schema normalization helpers (Pydantic v2 / JSON Schema)."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel, create_model

from docstruct.errors import SchemaError


def normalize_schema(
    schema: type[BaseModel] | dict[str, Any] | None,
) -> type[BaseModel] | None:
    """
    Accept a Pydantic model class or a JSON Schema dict and return
    a usable Pydantic model class (or None when no schema is given).
    """
    if schema is None:
        return None

    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema

    if isinstance(schema, dict):
        return _json_schema_to_model(schema)

    raise SchemaError(
        f"Unsupported schema type: {type(schema)}. "
        "Expected a Pydantic BaseModel subclass or a JSON Schema dict."
    )


def _json_schema_to_model(schema: dict[str, Any]) -> type[BaseModel]:
    """Very lightweight JSON Schema → dynamic Pydantic model (object only)."""
    if schema.get("type") not in (None, "object"):
        raise SchemaError("Only object-type JSON Schemas are supported for dynamic models.")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, Any] = {}
    for name, prop in properties.items():
        py_type = _json_type_to_python(prop)
        default = ... if name in required else None
        fields[name] = (py_type, default)

    model_name = schema.get("title", "DynamicSchema")
    return create_model(model_name, **fields)  # type: ignore[call-overload]


def _json_type_to_python(prop: dict[str, Any]) -> type:
    t = prop.get("type", "string")
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(t, Any)  # type: ignore[return-value]
