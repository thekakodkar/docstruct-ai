"""
Example 03 — Local open-weight VLM via Ollama

Prerequisites:
    1. Ollama running:  ollama serve
    2. A vision model:  ollama pull qwen2.5vl:7b

Run:
    python examples/03_local_ollama.py path/to/invoice.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydantic import BaseModel, Field

from docstruct import DocumentClient, OllamaProvider, RoutingPolicy


class LineItem(BaseModel):
    description: str = ""
    qty: float = 0.0
    unit_price: float = 0.0
    amount: float = 0.0


class Invoice(BaseModel):
    vendor: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    total: float = 0.0
    currency: str = "USD"
    lines: list[LineItem] = Field(default_factory=list)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/03_local_ollama.py <image-or-pdf>")
        print("(Requires Ollama with a vision model, e.g. qwen2.5vl:7b)")
        sys.exit(1)

    source = sys.argv[1]

    client = DocumentClient(
        providers=[
            OllamaProvider(
                model="qwen2.5vl:7b",
                base_url="http://localhost:11434",
                temperature=0.0,
            ),
        ],
        default_routing=RoutingPolicy(primary_provider="ollama"),
    )

    print(f"Extracting from {source} via Ollama …")
    result = client.extract(
        source,
        schema=Invoice,
        prompt_hint=(
            "Extract the vendor name, invoice number, date, currency, "
            "total amount, and every line item (description, qty, unit price, amount)."
        ),
    )

    print(result.to_json(indent=2, include_telemetry=True))
    print("\n--- XML ---")
    print(result.to_xml(root_tag="Invoice", list_item_tags={"lines": "Line"}))


if __name__ == "__main__":
    main()
