"""Routing policies, retry/escalation rules, and timeouts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from docstruct.models.ir import DocumentIR


class RoutingPolicy(BaseModel):
    """Controls provider selection, retries, and escalation behaviour."""

    primary_provider: str
    fallback_providers: list[str] = Field(default_factory=list)
    max_retries_per_provider: int = 1
    validation_rules: list[Callable[[BaseModel | dict[str, Any], DocumentIR], list[str]]] = Field(
        default_factory=list,
        exclude=True,
    )
    escalate_on_low_confidence: float | None = None
    timeout_seconds: float = 120.0
    prefer_local: bool = True

    model_config = {"arbitrary_types_allowed": True}
