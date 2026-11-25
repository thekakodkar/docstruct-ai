"""S3 helper unit tests (no AWS calls)."""

from __future__ import annotations

import pytest

from docstruct.io.s3 import parse_s3_uri


def test_parse_s3_uri_ok():
    bucket, key = parse_s3_uri("s3://my-bucket/path/to/file.pdf")
    assert bucket == "my-bucket"
    assert key == "path/to/file.pdf"


def test_parse_s3_uri_invalid():
    with pytest.raises(ValueError):
        parse_s3_uri("https://example.com/x")
    with pytest.raises(ValueError):
        parse_s3_uri("s3://bucket-only")


def test_client_missing_boto3_message(monkeypatch):
    import docstruct.io.s3 as s3mod

    def boom(*args, **kwargs):
        raise ImportError("No module named boto3")

    # Simulate boto3 missing by replacing the internal import path
    monkeypatch.setitem(__import__("sys").modules, "boto3", None)

    def fake_client():
        try:
            import boto3  # type: ignore
            if boto3 is None:
                raise ImportError("No module named boto3")
        except Exception as exc:
            raise ImportError(
                "S3 support requires the optional [s3] extra: pip install 'docstruct[s3]'"
            ) from exc

    monkeypatch.setattr(s3mod, "_client", fake_client)
    with pytest.raises(ImportError, match=r"docstruct\[s3\]"):
        s3mod._client()
