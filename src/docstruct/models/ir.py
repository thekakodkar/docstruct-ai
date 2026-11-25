"""Intermediate Document Representation (IR) models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box with coordinate space and page reference."""

    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_space: Literal["normalized", "pixel"] = "normalized"
    page_number: int = Field(..., ge=1, description="1-indexed page number")


class Block(BaseModel):
    """A semantic content block extracted from a page."""

    block_id: str
    kind: Literal["text", "heading", "table", "key_value", "formula", "figure"]
    content: Any
    bbox: BBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageIR(BaseModel):
    """Layout-aware representation of a single page."""

    page_number: int = Field(..., ge=1)
    width: float | None = None
    height: float | None = None
    blocks: list[Block] = Field(default_factory=list)
    raw_text: str | None = None
    image_path: str | None = None


class PageInput(BaseModel):
    """Input page fed to a provider (image bytes or path + metadata)."""

    page_number: int = Field(..., ge=1)
    image_bytes: bytes | None = None
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    mime_type: str = "image/png"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIR(BaseModel):
    """Canonical intermediate representation of an entire document."""

    source_name: str
    page_count: int
    pages: list[PageIR] = Field(default_factory=list)
    raw_markdown: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
