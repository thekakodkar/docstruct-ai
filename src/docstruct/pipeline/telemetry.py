"""Latency, cost estimation, and audit record helpers."""

from __future__ import annotations

from docstruct.models.result import ProvenanceRecord, Telemetry


def estimate_cost(
    provider: str,
    pages: int,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> float:
    """
    Rough cost estimator (USD).

    These are indicative defaults; override in production with real pricing.
    """
    # Very rough public pricing approximations (2025/2026)
    table = {
        "openai_compat": 0.01 * pages,  # placeholder
        "ollama": 0.0,
        "mock": 0.0,
        "http_ocr": 0.005 * pages,
    }
    base = table.get(provider, 0.01 * pages)
    if tokens_in or tokens_out:
        # add token-based component if known
        base += ((tokens_in or 0) + (tokens_out or 0)) * 0.000002
    return round(base, 6)


def merge_telemetry(*parts: Telemetry) -> Telemetry:
    """Combine multiple Telemetry objects (e.g. multi-batch runs)."""
    out = Telemetry()
    for t in parts:
        out.total_latency_ms += t.total_latency_ms
        out.total_estimated_cost_usd += t.total_estimated_cost_usd
        out.providers_used.extend(t.providers_used)
        out.pages_processed += t.pages_processed
        out.retries += t.retries
        out.escalations += t.escalations
        out.records.extend(t.records)
    return out
