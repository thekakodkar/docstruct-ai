"""Optional CLI: `docstruct extract doc.pdf --schema ... --format xml`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich import print as rprint
except ImportError:
    # CLI extra not installed
    def app() -> None:  # type: ignore[misc]
        print(
            "CLI requires the optional [cli] extra:\n"
            "  pip install 'docstruct[cli]'",
            file=sys.stderr,
        )
        sys.exit(1)

    if __name__ == "__main__":
        app()
else:
    app = typer.Typer(
        name="docstruct",
        help="Model-agnostic OCR & structured XML/JSON extraction.",
        add_completion=False,
    )

    @app.command()
    def extract(
        source: Path = typer.Argument(..., help="PDF or image path"),
        schema: Optional[Path] = typer.Option(None, "--schema", "-s", help="JSON Schema file"),
        format: str = typer.Option("json", "--format", "-f", help="json | xml | ndjson"),
        output: Optional[Path] = typer.Option(None, "--output", "-o"),
        provider: str = typer.Option("mock", "--provider", "-p"),
        root_tag: str = typer.Option("Document", "--root-tag"),
    ) -> None:
        """Extract structured data from a document."""
        from docstruct import DocumentClient, MockProvider, RoutingPolicy
        from docstruct.providers.ollama import OllamaProvider
        from docstruct.providers.openai_compat import OpenAICompatProvider

        providers = []
        if provider == "mock":
            providers.append(MockProvider())
        elif provider == "ollama":
            providers.append(OllamaProvider())
        else:
            providers.append(MockProvider())  # safe default

        client = DocumentClient(
            providers=providers,
            default_routing=RoutingPolicy(primary_provider=providers[0].name),
        )

        schema_obj = None
        if schema and schema.exists():
            schema_obj = json.loads(schema.read_text(encoding="utf-8"))

        result = client.extract(source, schema=schema_obj)

        if format == "xml":
            text = result.to_xml(root_tag=root_tag)
        elif format == "ndjson":
            from docstruct.serializers.json_serializer import to_ndjson

            text = to_ndjson([result])
        else:
            text = result.to_json(include_telemetry=True)

        if output:
            output.write_text(text, encoding="utf-8")
            rprint(f"[green]Wrote[/green] {output}")
        else:
            print(text)

    if __name__ == "__main__":
        app()
