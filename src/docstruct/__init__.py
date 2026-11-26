"""
docstruct - Model-agnostic OCR and structured extraction library.

Python 3.11+ | Open-Weight SLMs and Cloud VLMs | Deterministic Pydantic/XSD Schema Enforcement
"""

from __future__ import annotations

from docstruct.client import DocumentClient
from docstruct.config import RoutingPolicy
from docstruct.errors import (
    ProviderError,
    SchemaError,
    SerializationError,
    ValidationError,
)
from docstruct.models.ir import BBox, Block, DocumentIR, PageIR, PageInput
from docstruct.models.result import ExtractionResult, ProvenanceRecord, Telemetry, ValidationReport
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput
from docstruct.providers.http_ocr import HttpOCRProvider
from docstruct.providers.mock import MockProvider
from docstruct.providers.native import NativeTextProvider
from docstruct.providers.ollama import OllamaProvider
from docstruct.providers.openai_compat import OpenAICompatProvider

__version__ = "1.0.0"

__all__ = [
    "DocumentClient",
    "RoutingPolicy",
    "ProviderError",
    "SchemaError",
    "SerializationError",
    "ValidationError",
    "BBox",
    "Block",
    "DocumentIR",
    "PageIR",
    "PageInput",
    "ExtractionResult",
    "ProvenanceRecord",
    "Telemetry",
    "ValidationReport",
    "BaseOCRProvider",
    "ProviderCapabilities",
    "ProviderRawOutput",
    "MockProvider",
    "NativeTextProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "HttpOCRProvider",
    "extract",
    "__version__",
]


def extract(source, schema=None, *, provider: str = "mock", **kwargs):
    """
    Minimal one-call extraction.

    Examples
    --------
    >>> from docstruct import extract
    >>> result = extract("invoice.pdf", schema=Invoice)  # mock demo
    >>> result = extract("scan.png", schema=Invoice, provider="ollama")
    """
    if provider == "mock":
        client = DocumentClient.mock()
    elif provider == "ollama":
        client = DocumentClient.ollama()
    elif provider in {"openai", "openai_compat"}:
        client = DocumentClient.openai()
    elif provider == "native":
        client = DocumentClient(
            providers=[NativeTextProvider()],
            default_routing=RoutingPolicy(primary_provider="native"),
        )
    else:
        raise ValueError(f"Unknown provider shortcut: {provider!r}. Use DocumentClient(...).")
    return client.extract(source, schema=schema, **kwargs)
