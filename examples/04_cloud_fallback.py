"""
Example 04 — Local-first with cloud fallback

Tries Ollama first. If validation fails or confidence is low,
automatically escalates to an OpenAI-compatible endpoint.

Set OPENAI_API_KEY in the environment (or pass api_key= explicitly).

Run:
    export OPENAI_API_KEY=sk-...
    python examples/04_cloud_fallback.py path/to/doc.pdf
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydantic import BaseModel

from docstruct import (
    DocumentClient,
    OllamaProvider,
    OpenAICompatProvider,
    RoutingPolicy,
)


class Extraction(BaseModel):
    title: str = ""
    summary: str = ""
    key_fields: dict[str, str] = {}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/04_cloud_fallback.py <document>")
        sys.exit(1)

    source = sys.argv[1]
    api_key = os.environ.get("OPENAI_API_KEY")

    providers = [
        OllamaProvider(model="qwen2.5vl:7b"),
    ]
    if api_key:
        providers.append(
            OpenAICompatProvider(
                model="gpt-4o",
                base_url="https://api.openai.com/v1",
                api_key=api_key,
            )
        )

    client = DocumentClient(
        providers=providers,
        default_routing=RoutingPolicy(
            primary_provider="ollama",
            fallback_providers=["openai_compat"] if api_key else [],
            max_retries_per_provider=1,
            escalate_on_low_confidence=0.65,
        ),
    )

    result = client.extract(source, schema=Extraction)
    print(result.to_json(indent=2, include_telemetry=True))
    print(f"\nProviders used: {result.telemetry.providers_used}")
    print(f"Escalations   : {result.telemetry.escalations}")
    print(f"Retries       : {result.telemetry.retries}")


if __name__ == "__main__":
    main()
