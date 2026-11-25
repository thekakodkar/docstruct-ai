"""Provider adapters."""

from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput
from docstruct.providers.http_ocr import HttpOCRProvider
from docstruct.providers.mock import MockProvider
from docstruct.providers.native import NativeTextProvider
from docstruct.providers.ollama import OllamaProvider
from docstruct.providers.openai_compat import OpenAICompatProvider

__all__ = [
    "BaseOCRProvider",
    "ProviderCapabilities",
    "ProviderRawOutput",
    "MockProvider",
    "NativeTextProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "HttpOCRProvider",
]
