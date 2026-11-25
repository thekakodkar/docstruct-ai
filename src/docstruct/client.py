"""High-level DocumentClient entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from pydantic import BaseModel

from docstruct.config import RoutingPolicy
from docstruct.models.result import ExtractionResult
from docstruct.pipeline.ingest import load_native_document, load_pages
from docstruct.pipeline.router import ExtractionRouter
from docstruct.providers.base import BaseOCRProvider


class DocumentClient:
    """
    Ergonomic façade for structured document extraction.

    Example
    -------
    >>> client = DocumentClient(
    ...     providers=[MockProvider()],
    ...     default_routing=RoutingPolicy(primary_provider="mock"),
    ... )
    >>> result = client.extract("invoice.pdf", schema=InvoiceSchema)
    >>> print(result.to_json())
    """

    def __init__(
        self,
        providers: list[BaseOCRProvider],
        default_routing: RoutingPolicy | None = None,
    ) -> None:
        self._providers: dict[str, BaseOCRProvider] = {p.name: p for p in providers}
        if not self._providers:
            raise ValueError("At least one provider is required")

        primary = next(iter(self._providers))
        self.default_routing = default_routing or RoutingPolicy(primary_provider=primary)

    def register_provider(self, provider: BaseOCRProvider) -> None:
        self._providers[provider.name] = provider


    def _resolve_source(self, source: str | Path | bytes | BinaryIO):
        """Resolve s3:// URIs to bytes when needed."""
        if isinstance(source, str) and source.startswith("s3://"):
            from docstruct.io.s3 import read_bytes

            return read_bytes(source)
        return source

    async def aextract(
        self,
        source: str | Path | bytes | BinaryIO,
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        rules: list | None = None,
        routing: RoutingPolicy | None = None,
        prompt_hint: str | None = None,
        dpi: int = 200,
        max_pages: int | None = None,
    ) -> ExtractionResult:
        """Async extraction entry point."""
        source = self._resolve_source(source)
        pages = load_pages(source, dpi=dpi, max_pages=max_pages)
        source_name = str(source) if isinstance(source, (str, Path)) else "document"
        policy = routing or self.default_routing
        router = ExtractionRouter(self._providers, policy)
        return await router.run(
            pages,
            schema=schema,
            rules=rules,
            source_name=source_name,
            prompt_hint=prompt_hint,
        )

    def extract(
        self,
        source: str | Path | bytes | BinaryIO,
        *,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        rules: list | None = None,
        routing: RoutingPolicy | None = None,
        prompt_hint: str | None = None,
        dpi: int = 200,
        max_pages: int | None = None,
    ) -> ExtractionResult:
        """Synchronous convenience wrapper."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # nested case – create a new loop in a thread (simple path)
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.aextract(
                        source,
                        schema=schema,
                        rules=rules,
                        routing=routing,
                        prompt_hint=prompt_hint,
                        dpi=dpi,
                        max_pages=max_pages,
                    ),
                )
                return future.result()
        return asyncio.run(
            self.aextract(
                source,
                schema=schema,
                rules=rules,
                routing=routing,
                prompt_hint=prompt_hint,
                dpi=dpi,
                max_pages=max_pages,
            )
        )

    def extract_native(
        self,
        source: str | Path | bytes | BinaryIO,
        *,
        max_pages: int | None = None,
    ) -> dict:
        """
        Text-first extraction for digital PDF / DOCX / PPTX without a vision model.

        Returns a dict with pages, markdown, and format metadata.
        """
        source = self._resolve_source(source)
        return load_native_document(source, max_pages=max_pages)

