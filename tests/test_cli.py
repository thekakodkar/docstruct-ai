"""CLI smoke tests."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

typer = pytest.importorskip("typer")
from typer.testing import CliRunner

from docstruct.cli import app


runner = CliRunner()


def _png(path: Path) -> Path:
    img = Image.new("RGB", (40, 40), color="white")
    img.save(path)
    return path


def test_cli_extract_json(tmp_path: Path):
    src = _png(tmp_path / "doc.png")
    result = runner.invoke(
        app,
        ["extract", str(src), "--provider", "mock", "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    assert "ACME Corp" in result.output or "vendor" in result.output


def test_cli_extract_xml_to_file(tmp_path: Path):
    src = _png(tmp_path / "doc.png")
    out = tmp_path / "out.xml"
    result = runner.invoke(
        app,
        [
            "extract",
            str(src),
            "--provider",
            "mock",
            "--format",
            "xml",
            "--root-tag",
            "Invoice",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "<Invoice>" in text
    assert "ACME" in text or "vendor" in text
