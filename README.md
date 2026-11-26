# docstruct-ai v1.0.0

**Model-agnostic OCR and structured extraction for PDFs, images, DOCX, and PPTX.**

Python 3.11+ · Open-weight SLMs and cloud VLMs · Deterministic Pydantic / XSD enforcement

[![PyPI](https://img.shields.io/pypi/v/docstruct-ai.svg)](https://pypi.org/project/docstruct-ai/)
[![Python](https://img.shields.io/pypi/pyversions/docstruct-ai.svg)](https://pypi.org/project/docstruct-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

- **PyPI:** https://pypi.org/project/docstruct-ai/
- **GitHub:** https://github.com/thekakodkar/docstruct-ai
- **Docs:** https://thekakodkar.github.io/docstruct-ai/

Install as `docstruct-ai`. Import as `docstruct`.

---

## Extract an invoice in 4 lines

```python
from docstruct import DocumentClient, MockProvider, RoutingPolicy
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str

client = DocumentClient(
    providers=[MockProvider()],
    default_routing=RoutingPolicy(primary_provider="mock"),
)
result = client.extract("invoice.pdf", schema=Invoice)
print(result.to_json())
print(result.to_xml(root_tag="Invoice", list_item_tags={"lines": "Line"}))
print(result.to_markdown(title="Invoice"))
```

---


## What is new in 1.0.0

- Stable public API and versioned release
- One-call `extract()` plus `DocumentClient.ollama()` / `.openai()` / `.mock()`
- Exponential backoff on provider and validation retries
- Batch extraction via `client.extract_batch([...])`
- Safer defaults: file size cap, page cap, Office zip bomb guard
- Markdown, native DOCX/PPTX, optional S3

## Minimal usage

```python
from docstruct import extract
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    total: float

# Offline demo (no model server)
result = extract("invoice.pdf", schema=Invoice)

# Local Ollama
result = extract("scan.png", schema=Invoice, provider="ollama")

# OpenAI-compatible (reads OPENAI_API_KEY from the environment)
result = extract("form.pdf", schema=Invoice, provider="openai")

print(result.to_json())
```

Or construct a client once:

```python
from docstruct import DocumentClient

client = DocumentClient.ollama()          # or .openai() / .mock()
result = client.extract("invoice.pdf", schema=Invoice)
```

## Which method should I use?

| Your use case | Method | Best for |
|---|---|---|
| One-shot extraction with schema | `client.extract(path, schema=Model)` | Most apps |
| Async high-throughput | `await client.aextract(...)` | FastAPI, workers |
| Native text only (no VLM) | `client.extract_native(path)` | Digital PDF / DOCX / PPTX |
| Validated objects | `result.data` | Business logic |
| JSON | `result.to_json()` | APIs |
| NDJSON | `to_ndjson([result, ...])` | Lakehouse, Kafka |
| XML | `result.to_xml(...)` | ERP, EDI, XSD |
| Markdown | `result.to_markdown()` | Docs, RAG |
| Audit trail | `result.telemetry` / `result.validation` | Governance |

---

## Installation

```bash
# Core (Pydantic + httpx + Pillow)
pip install docstruct-ai

# PDF rendering (PyMuPDF)
pip install "docstruct-ai[pdf]"

# XSD validation (lxml)
pip install "docstruct-ai[xml]"

# S3 read/write (boto3)
pip install "docstruct-ai[s3]"

# CLI
pip install "docstruct-ai[cli]"

# Streamlit playground
pip install "docstruct-ai[playground]"

# Everything
pip install "docstruct-ai[all]"
```

Also installs the `docstruct` CLI (`python -m docstruct`).

### Supported inputs and outputs

| Inputs | Outputs | Optional cloud |
|--------|---------|----------------|
| PDF (digital + scanned), PNG/JPEG/WebP/TIFF | JSON, NDJSON, XML, Markdown | S3 (`docstruct-ai[s3]`) |
| DOCX, PPTX (native text via stdlib) | Provenance + validation telemetry | |

Native text path (no VLM):

```python
client.extract_native("report.docx")  # pages + markdown
```

S3:

```python
from docstruct.io import read_bytes, write_extraction

data = read_bytes("s3://bucket/in/invoice.pdf")
write_extraction(result, "s3://bucket/out/invoice.json", format="json")
```

---

## Design principles

1. **Model and runtime agnostic** - Ollama, OpenAI-compatible servers, Docling, MinerU, and cloud VLMs share one contract.
2. **Schema-first and deterministic** - Pydantic v2 / JSON Schema, business rules, repair, and escalation.
3. **JSON, XML, and Markdown** - Deterministic JSON, NDJSON, configurable XML, Markdown export.
4. **Provenance and telemetry** - Pages, bboxes, confidence, latency, cost, validation reports.
5. **Clean core** - Optional extras for PDF, XML, S3, CLI, and playground.

---

## Use cases

### 1. Local open-weight VLM (Ollama)

```python
from docstruct import DocumentClient, OllamaProvider, RoutingPolicy
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str = "USD"

client = DocumentClient(
    providers=[OllamaProvider(model="qwen2.5vl:7b")],
    default_routing=RoutingPolicy(primary_provider="ollama"),
)
result = client.extract("scanned_invoice.pdf", schema=Invoice)
print(result.to_json(include_telemetry=True))
```

### 2. Local-first with cloud fallback

```python
from docstruct import (
    DocumentClient, OllamaProvider, OpenAICompatProvider, RoutingPolicy
)

client = DocumentClient(
    providers=[
        OllamaProvider(model="qwen2.5vl:7b"),
        OpenAICompatProvider(
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key="sk-...",
        ),
    ],
    default_routing=RoutingPolicy(
        primary_provider="ollama",
        fallback_providers=["openai_compat"],
        max_retries_per_provider=1,
        escalate_on_low_confidence=0.7,
    ),
)
result = client.extract("complex_form.pdf", schema=MySchema)
```

### 3. Custom business rules

```python
from docstruct.models.ir import DocumentIR
from pydantic import BaseModel

def check_line_items_sum_to_total(data: BaseModel, ir: DocumentIR) -> list[str]:
    if not hasattr(data, "lines") or not hasattr(data, "total"):
        return []
    calculated = sum(line.amount for line in data.lines)
    if abs(calculated - data.total) > 0.01:
        return [f"Line items sum ({calculated}) does not equal total ({data.total})"]
    return []

result = client.extract("invoice.pdf", schema=Invoice, rules=[check_line_items_sum_to_total])
```

### 4. XML with namespaces and attributes

```python
xml = result.to_xml(
    root_tag="Invoice",
    list_item_tags={"lines": "Line"},
    attribute_fields={"currency", "invoice_number"},
    namespaces={"inv": "http://example.com/invoice/v1"},
    pretty=True,
)
```

### 5. Streaming NDJSON

```python
from docstruct.serializers import to_ndjson

results = [client.extract(f) for f in pdf_files]
with open("invoices.ndjson", "w", encoding="utf-8") as f:
    f.write(to_ndjson(results))
```

### 6. Generic HTTP OCR (Docling / MinerU / PaddleOCR-VL)

```python
from docstruct import DocumentClient, HttpOCRProvider, RoutingPolicy

client = DocumentClient(
    providers=[HttpOCRProvider(endpoint="http://localhost:8000/extract", name="docling")],
    default_routing=RoutingPolicy(primary_provider="docling"),
)
```

### 7. CLI

```bash
docstruct extract invoice.pdf --schema schema.json --format json -o out.json
docstruct extract invoice.pdf --format xml --root-tag Invoice -o out.xml
docstruct extract scan.png --provider ollama --format json
```

### 8. Playground (real PDFs)

```bash
pip install "docstruct-ai[pdf,playground]"
streamlit run examples/playground.py
```

---

## Architecture

```
docstruct/
├── client.py              # DocumentClient
├── config.py              # RoutingPolicy
├── io/s3.py               # Optional S3 helpers
├── models/                # IR, result, schema
├── providers/             # mock, native, ollama, openai_compat, http_ocr
├── pipeline/              # ingest, router, validator, telemetry
└── serializers/           # json, xml, markdown
```

---

## Provider matrix

| Provider | Structured JSON | BBoxes | PDF native | Typical use |
|---|---|---|---|---|
| MockProvider | Yes | Yes | - | Tests, demos |
| NativeTextProvider | Yes | - | Yes | Digital PDF / DOCX / PPTX |
| OllamaProvider | Yes | - | - | Local privacy |
| OpenAICompatProvider | Yes | - | - | GPT-4o, vLLM, LM Studio |
| HttpOCRProvider | Yes | Yes | Configurable | Docling, MinerU, PaddleOCR-VL |

---

## Error handling

```python
from docstruct import ValidationError, ProviderError

try:
    result = client.extract("bad.pdf", schema=Invoice)
except ValidationError as e:
    print(e.errors, e.attempts)
except ProviderError as e:
    print(e.provider, e.status_code)
```

```python
result.validation.is_valid
result.validation.errors
result.validation.attempts
```

---

## Testing

```bash
pip install -e ".[dev]"
pytest
```

---

## Where this fits

docstruct-ai is a **thin orchestration layer** (ingest, route, validate, serialize). It is not a full document AI platform.

| Tool | Strength | Overlap |
|------|----------|---------|
| **docstruct-ai** | Schema-first extraction, multi-provider routing, JSON/XML/MD, native Office text | You are here |
| Unstructured / LlamaParse | Broad connectors, hosted parsing | Heavier; less schema-deterministic |
| Docling / MinerU | Strong layout PDF parsing | Use via `HttpOCRProvider` |
| BODtoJSON | Infor OAGIS BOD → flat JSON | Complementary downstream of extraction |

Best when you want **small dependency surface**, **Pydantic contracts**, and **swap models without rewriting app code**.

## License

MIT License. Author: [Niraj Kakodkar](https://www.linkedin.com/in/thekakodkar/).
