"""
docstruct — Model-agnostic OCR & structured XML/JSON extraction library.

Python 3.11+ | Open-Weight SLMs & Cloud VLMs | Deterministic Pydantic/XSD Schema Enforcement
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
from docstruct.providers.mock import MockProvider
from docstruct.providers.ollama import OllamaProvider
from docstruct.providers.openai_compat import OpenAICompatProvider
from docstruct.providers.http_ocr import HttpOCRProvider

__version__ = "0.1.0"

__all__ = [
    # Public API
    "DocumentClient",
    "RoutingPolicy",
    # Errors
    "ProviderError",
    "SchemaError",
    "SerializationError",
    "ValidationError",
    # IR
    "BBox",
    "Block",
    "DocumentIR",
    "PageIR",
    "PageInput",
    # Result
    "ExtractionResult",
    "ProvenanceRecord",
    "Telemetry",
    "ValidationReport",
    # Providers
    "BaseOCRProvider",
    "ProviderCapabilities",
    "ProviderRawOutput",
    "MockProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "HttpOCRProvider",
    "__version__",
]
