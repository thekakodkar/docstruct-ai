"""Local Ollama VLM / OCR adapter."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from pydantic import BaseModel

from docstruct.errors import ProviderError
from docstruct.models.ir import PageInput
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput


class OllamaProvider(BaseOCRProvider):
    """Adapter for Ollama vision / multimodal models (qwen2.5vl, llava, etc.)."""

    name = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        temperature: float = 0.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.capabilities = ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=False,
            supports_pdf_native=False,
            max_pages_per_call=4,
        )

    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        start = time.perf_counter()
        images_b64: list[str] = []
        for p in pages:
            if p.image_bytes:
                images_b64.append(base64.b64encode(p.image_bytes).decode("ascii"))
            elif p.image_path:
                with open(p.image_path, "rb") as f:
                    images_b64.append(base64.b64encode(f.read()).decode("ascii"))
            else:
                raise ProviderError("PageInput must supply image_bytes or image_path", provider=self.name)

        system = (
            "You are a precise document extraction engine. "
            "Return only valid JSON matching the requested schema. "
            "Do not invent values."
        )
        if schema is not None:
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                schema_hint = schema.model_json_schema()
            else:
                schema_hint = schema
            system += f"\n\nJSON Schema:\n{schema_hint}"

        user_prompt = prompt_hint or "Extract all structured fields from this document."

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": images_b64,
                },
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}", provider=self.name, cause=exc) from exc

        content_str = data.get("message", {}).get("content", "{}")
        latency_ms = (time.perf_counter() - start) * 1000

        import json

        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            content = {"raw_text": content_str}

        return ProviderRawOutput(
            content=content,
            latency_ms=latency_ms,
            model=self.model,
            provider_metadata={"ollama_response": data.get("model")},
        )
