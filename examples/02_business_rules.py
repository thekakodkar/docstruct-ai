"""
Example 02 — Custom business validation rules

Demonstrates a rule that checks line-item amounts sum to the invoice total.
On failure the router retries / escalates (here we just show the error).

Run:
    python examples/02_business_rules.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from pydantic import BaseModel

from docstruct import DocumentClient, MockProvider, RoutingPolicy, ValidationError
from docstruct.models.ir import DocumentIR


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


def check_line_items_sum_to_total(data: Invoice, ir: DocumentIR) -> list[str]:
    """Return error messages if line items do not sum to total."""
    calculated = sum(line.amount for line in data.lines)
    if abs(calculated - data.total) > 0.01:
        return [
            f"Line items sum ({calculated:.2f}) does not equal total ({data.total:.2f})"
        ]
    return []


def main() -> None:
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    # --- Happy path (mock data already sums correctly) ---
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock", max_retries_per_provider=0),
    )
    result = client.extract(png, schema=Invoice, rules=[check_line_items_sum_to_total])
    print("Happy path valid:", result.validation.is_valid)
    print(result.to_json(indent=2))

    # --- Force a mismatch ---
    bad_provider = MockProvider(
        payload={
            "vendor": "Bad Corp",
            "invoice_number": "BAD-1",
            "total": 9999.0,  # does not match lines
            "currency": "USD",
            "lines": [
                {"description": "A", "qty": 1, "unit_price": 10, "amount": 10.0},
            ],
        }
    )
    client_bad = DocumentClient(
        providers=[bad_provider],
        default_routing=RoutingPolicy(primary_provider="mock", max_retries_per_provider=0),
    )
    try:
        client_bad.extract(png, schema=Invoice, rules=[check_line_items_sum_to_total])
    except ValidationError as e:
        print("\nExpected validation failure:")
        for err in e.errors:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
