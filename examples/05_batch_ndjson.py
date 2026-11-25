"""
Example 05 — Batch extraction → NDJSON stream

Ideal for Snowflake Snowpipe, Databricks Auto Loader, Kafka, or RAG pipelines.

Run:
    python examples/05_batch_ndjson.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from pydantic import BaseModel

from docstruct import DocumentClient, MockProvider, RoutingPolicy
from docstruct.serializers import to_ndjson


class Record(BaseModel):
    vendor: str
    invoice_number: str
    total: float


def main() -> None:
    client = DocumentClient(
        providers=[MockProvider()],
        default_routing=RoutingPolicy(primary_provider="mock"),
    )

    # Simulate a batch of 5 documents
    results = []
    for i in range(5):
        img = Image.new("RGB", (64, 64), color=(i * 40, 100, 150))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = client.extract(buf.getvalue(), schema=Record)
        results.append(result)

    stream = to_ndjson(results, include_telemetry=False)
    out = Path("invoices.ndjson")
    out.write_text(stream, encoding="utf-8")

    print(f"Wrote {len(results)} records → {out.resolve()}")
    print("--- preview (first 2 lines) ---")
    for line in stream.strip().split("\n")[:2]:
        print(line)


if __name__ == "__main__":
    main()
