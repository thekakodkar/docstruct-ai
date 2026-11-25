"""Abstract base provider and shared contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from docstruct.models.ir import PageInput


class ProviderCapabilities(BaseModel):
    """Capability flags advertised by a provider."""

    supports_structured_json: bool = False
    supports_bboxes: bool = False
    supports_pdf_native: bool = False
    max_pages_per_call: int | None = None
    supports_async: bool = True


class ProviderRawOutput(BaseModel):
    """Raw response returned by a provider before schema validation."""

    content: dict[str, Any] | str
    pages: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    latency_ms: float | None = None
    model: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    bboxes: list[dict[str, Any]] = Field(default_factory=list)


class BaseOCRProvider(ABC):
    """Uniform contract implemented by every local and cloud backend."""

    name: str
    capabilities: ProviderCapabilities

    @abstractmethod
    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        """Extract structured content from one or more page images."""
        ...

    def extract_pages_sync(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        """Synchronous convenience wrapper."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.extract_pages(pages, schema=schema, prompt_hint=prompt_hint)
        )
