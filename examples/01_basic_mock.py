"""
Example 01 — Basic extraction with MockProvider

Run:
    python examples/01_basic_mock.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Allow running without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from pydantic import BaseModel

from docstruct import DocumentClient, MockProvider, RoutingPolicy


class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float


class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str = "USD"
    lines: list[LineItem] = []


def main() -> None:
    # Create a blank image as stand-in for a real document page
    img = Image.new("RGB", (200, 280), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )

    result = client.extract(buf.getvalue(), schema=Invoice)

    print("=== JSON ===")
    print(result.to_json(indent=2))

    print("\n=== XML ===")
    print(
        result.to_xml(
            root_tag="Invoice",
            list_item_tags={"lines": "Line"},
            pretty=True,
        )
    )

    print("\n=== Telemetry ===")
    print(f"  Providers used : {result.telemetry.providers_used}")
    print(f"  Latency (ms)   : {result.telemetry.total_latency_ms:.1f}")
    print(f"  Valid          : {result.validation.is_valid}")


if __name__ == "__main__":
    main()
