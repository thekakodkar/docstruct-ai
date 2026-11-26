"""Routing, fallback, and escalation policy execution."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from docstruct.config import RoutingPolicy
from docstruct.errors import ProviderError, ValidationError
from docstruct.models.ir import DocumentIR, PageInput, PageIR
from docstruct.models.result import ExtractionResult, ProvenanceRecord, Telemetry, ValidationReport
from docstruct.pipeline.validator import build_repair_prompt, validate_and_parse
from docstruct.providers.base import BaseOCRProvider


class ExtractionRouter:
    """Orchestrates provider selection, retries, validation, and escalation."""

    def __init__(
        self,
        providers: dict[str, BaseOCRProvider],
        policy: RoutingPolicy,
    ) -> None:
        self.providers = providers
        self.policy = policy

    async def run(
        self,
        pages: list[PageInput],
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        rules: list | None = None,
        source_name: str = "document",
        prompt_hint: str | None = None,
    ) -> ExtractionResult:
        order = [self.policy.primary_provider] + list(self.policy.fallback_providers)
        telemetry = Telemetry()
        last_errors: list[str] = []
        last_raw: Any = None
        attempts = 0

        for provider_name in order:
            provider = self.providers.get(provider_name)
            if provider is None:
                continue

            for attempt in range(self.policy.max_retries_per_provider + 1):
                attempts += 1
                repair_hint = None
                if attempt > 0 and last_errors:
                    repair_hint = build_repair_prompt(last_errors, last_raw)

                effective_hint = prompt_hint
                if repair_hint:
                    effective_hint = (prompt_hint or "") + "\n\n" + repair_hint

                t0 = time.perf_counter()
                try:
                    raw = await provider.extract_pages(
                        pages,
                        schema=schema,
                        prompt_hint=effective_hint,
                    )
                except ProviderError as exc:
                    last_errors = [str(exc)]
                    telemetry.retries += 1
                    delay = min(
                        self.policy.backoff_base_seconds * (2 ** attempt),
                        self.policy.backoff_max_seconds,
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue

                latency = (time.perf_counter() - t0) * 1000
                telemetry.total_latency_ms += latency
                telemetry.providers_used.append(provider_name)
                if raw.latency_ms:
                    # prefer provider-reported
                    pass

                # Build minimal IR
                ir = DocumentIR(
                    source_name=source_name,
                    page_count=len(pages),
                    pages=[
                        PageIR(page_number=p.page_number, width=p.width, height=p.height)
                        for p in pages
                    ],
                    provider_metadata=raw.provider_metadata,
                )

                content = raw.content if isinstance(raw.content, dict) else {"raw": raw.content}
                parsed, report = validate_and_parse(
                    content,
                    schema=schema,
                    rules=rules or self.policy.validation_rules,
                    ir=ir,
                )
                report.attempts = attempts

                telemetry.records.append(
                    ProvenanceRecord(
                        provider=provider_name,
                        model=raw.model,
                        page_numbers=[p.page_number for p in pages],
                        confidence=raw.confidence,
                        latency_ms=latency,
                        bboxes=raw.bboxes,
                    )
                )
                telemetry.pages_processed = len(pages)

                if report.is_valid:
                    # Optional confidence escalation
                    if (
                        self.policy.escalate_on_low_confidence is not None
                        and raw.confidence is not None
                        and raw.confidence < self.policy.escalate_on_low_confidence
                    ):
                        telemetry.escalations += 1
                        last_errors = [f"Confidence {raw.confidence} below threshold"]
                        continue

                    return ExtractionResult(
                        data=parsed,
                        ir=ir,
                        validation=report,
                        telemetry=telemetry,
                        schema_name=getattr(schema, "__name__", None) if schema else None,
                    )

                last_errors = report.errors
                last_raw = content
                telemetry.retries += 1
                delay = min(
                    self.policy.backoff_base_seconds * (2 ** attempt),
                    self.policy.backoff_max_seconds,
                )
                if delay > 0 and attempt < self.policy.max_retries_per_provider:
                    await asyncio.sleep(delay)

            # exhausted retries for this provider - escalate
            telemetry.escalations += 1

        raise ValidationError(
            f"All providers exhausted. Last errors: {last_errors}",
            errors=last_errors,
            attempts=attempts,
        )
