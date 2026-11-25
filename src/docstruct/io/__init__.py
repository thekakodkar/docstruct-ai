"""I/O helpers (local + optional S3)."""

from docstruct.io.s3 import (
    parse_s3_uri,
    read_bytes,
    write_bytes,
    write_extraction,
    write_json,
    write_text,
)

__all__ = [
    "parse_s3_uri",
    "read_bytes",
    "write_bytes",
    "write_text",
    "write_json",
    "write_extraction",
]
