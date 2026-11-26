"""OpenAI-compatible VLM / OCR provider (vLLM, LM Studio, OpenAI, Azure, etc.)."""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel

from docstruct.errors import ProviderError
from docstruct.models.ir import PageInput
from docstruct.providers.base import BaseOCRProvider, ProviderCapabilities, ProviderRawOutput


class OpenAICompatProvider(BaseOCRProvider):
    """Works with any OpenAI-compatible /v1/chat/completions endpoint."""

    name = "openai_compat"

    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout: float = 120.0,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DOCSTRUCT_API_KEY")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capabilities = ProviderCapabilities(
            supports_structured_json=True,
            supports_bboxes=False,
            supports_pdf_native=False,
            max_pages_per_call=8,
        )

    async def extract_pages(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        prompt_hint: str | None = None,
    ) -> ProviderRawOutput:
        start = time.perf_counter()

        content_parts: list[dict[str, Any]] = [
            {"type": "text", "text": prompt_hint or "Extract structured data from this document as JSON."}
        ]

        for p in pages:
            if p.image_bytes:
                b64 = base64.b64encode(p.image_bytes).decode("ascii")
            elif p.image_path:
                with open(p.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            else:
                raise ProviderError("PageInput requires image_bytes or image_path", provider=self.name)
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise document extraction engine. "
                    "Return only valid JSON. Never invent values."
                ),
            },
            {"role": "user", "content": content_parts},
        ]

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Prefer native structured output when available
        if schema is not None and isinstance(schema, type) and issubclass(schema, BaseModel):
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": True,
                },
            }
        else:
            body["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI-compat request failed: {exc}",
                provider=self.name,
                cause=exc,
            ) from exc

        raw = data["choices"][0]["message"]["content"]
        latency_ms = (time.perf_counter() - start) * 1000

        try:
            content = json.loads(raw)
        except json.JSONDecodeError:
            content = {"raw_text": raw}

        return ProviderRawOutput(
            content=content,
            latency_ms=latency_ms,
            model=self.model,
            provider_metadata={"usage": data.get("usage")},
        )
