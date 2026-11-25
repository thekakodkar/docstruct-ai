"""Optional AWS S3 helpers for reading sources and writing extraction outputs."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse


def _client(region: str | None = None, endpoint_url: str | None = None):
    try:
        import boto3
    except ImportError as exc:
        raise ImportError(
            "S3 support requires the optional [s3] extra: pip install 'docstruct[s3]'"
        ) from exc
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url)


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Not an s3 URI: {uri}")
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid s3 URI (need bucket and key): {uri}")
    return bucket, key


def read_bytes(
    uri_or_bucket: str,
    key: str | None = None,
    *,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> bytes:
    """
    Download object bytes from S3.

    Accepts either:
    - read_bytes("s3://bucket/path/file.pdf")
    - read_bytes("bucket", "path/file.pdf")
    """
    if key is None:
        bucket, key = parse_s3_uri(uri_or_bucket)
    else:
        bucket = uri_or_bucket
    client = _client(region=region, endpoint_url=endpoint_url)
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def write_bytes(
    data: bytes,
    uri_or_bucket: str,
    key: str | None = None,
    *,
    content_type: str | None = None,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> str:
    """Upload bytes to S3. Returns the s3:// URI written."""
    if key is None:
        bucket, key = parse_s3_uri(uri_or_bucket)
    else:
        bucket = uri_or_bucket
    client = _client(region=region, endpoint_url=endpoint_url)
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return f"s3://{bucket}/{key}"


def write_text(
    text: str,
    uri_or_bucket: str,
    key: str | None = None,
    *,
    content_type: str = "text/plain; charset=utf-8",
    region: str | None = None,
    endpoint_url: str | None = None,
) -> str:
    return write_bytes(
        text.encode("utf-8"),
        uri_or_bucket,
        key,
        content_type=content_type,
        region=region,
        endpoint_url=endpoint_url,
    )


def write_json(
    payload: Any,
    uri_or_bucket: str,
    key: str | None = None,
    *,
    indent: int | None = 2,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> str:
    body = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    return write_text(
        body,
        uri_or_bucket,
        key,
        content_type="application/json; charset=utf-8",
        region=region,
        endpoint_url=endpoint_url,
    )


def write_extraction(
    result: Any,
    uri_or_bucket: str,
    key: str | None = None,
    *,
    format: str = "json",
    region: str | None = None,
    endpoint_url: str | None = None,
) -> str:
    """
    Write an ExtractionResult (or dict) to S3 as json, ndjson, xml, or markdown.
    """
    fmt = format.lower()
    if hasattr(result, "to_json") and fmt == "json":
        text = result.to_json(include_telemetry=True)
        ctype = "application/json; charset=utf-8"
    elif hasattr(result, "to_xml") and fmt == "xml":
        text = result.to_xml()
        ctype = "application/xml; charset=utf-8"
    elif hasattr(result, "to_markdown") and fmt in {"md", "markdown"}:
        text = result.to_markdown(include_telemetry=True)
        ctype = "text/markdown; charset=utf-8"
    elif fmt == "json":
        text = json.dumps(result, indent=2, default=str)
        ctype = "application/json; charset=utf-8"
    else:
        text = str(result)
        ctype = "text/plain; charset=utf-8"
    return write_text(
        text,
        uri_or_bucket,
        key,
        content_type=ctype,
        region=region,
        endpoint_url=endpoint_url,
    )
