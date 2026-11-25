# docstruct v0.2.0 
**Model-Agnostic OCR & Structured XML/JSON Library**

Documentation https://thekakodkar.github.io/docstruct/

<img width="769" height="336" alt="image" src="https://github.com/user-attachments/assets/5851aa9b-7041-4cd7-b823-61e7a11085a1" />


Python 3.11+ · Open-Weight SLMs & Cloud VLMs · Deterministic Pydantic/XSD Schema Enforcement

---

# docstruct: Extract Structured Data from Any Document

Turn PDFs, scanned pages, and images into **validated JSON, streaming NDJSON, or compliant XML** with a single unified interface. Swap local open-weight VLMs (Ollama, vLLM, LM Studio) and cloud vision APIs without changing your application code. Every extraction is schema-enforced, provenance-tracked, and ready for downstream systems.

**Schema-First** · **Provider Agnostic** · **Local-First Routing** · **Full Provenance** · **XML + JSON Native** · **Zero Hard-Coded Vendor Logic**

---

## Extract an Invoice in 4 Lines

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
```

**Output (abridged):**

```json
{
  "currency": "USD",
  "invoice_number": "INV-1001",
  "total": 1250.0,
  "vendor": "ACME Corp"
}
```

```xml
<?xml version="1.0" ?>
<Invoice>
  <vendor>ACME Corp</vendor>
  <invoice_number>INV-1001</invoice_number>
  <total>1250.0</total>
  <currency>USD</currency>
</Invoice>
```

---

## Which Method Should I Use?

| Your Use Case | Function / Method | Return Type | Best For |
|---|---|---|---|
| **One-shot extraction with schema** | `client.extract(path, schema=Model)` | `ExtractionResult` | Most applications – start here |
| **Async high-throughput** | `await client.aextract(...)` | `ExtractionResult` | FastAPI, batch workers, concurrent pipelines |
| **Validated Python objects** | `result.data` | `BaseModel` or `dict` | Business logic, DB inserts |
| **Clean JSON string** | `result.to_json()` | `str` | APIs, document stores, logging |
| **Streaming NDJSON** | `to_ndjson([result, ...])` | `str` | Snowflake, Databricks, Kafka, RAG |
| **Compliant XML** | `result.to_xml(root_tag=..., list_item_tags=...)` | `str` | ERP, EDI, legacy integrations, XSD |
| **Full audit trail** | `result.telemetry` / `result.validation` | models | Governance, cost tracking, retries |

---

## Installation

```bash
# Core library (Pydantic + httpx + Pillow)
pip install docstruct

# With PDF rendering (PyMuPDF)
pip install "docstruct[pdf]"

# With XSD validation (lxml)
pip install "docstruct[xml]"

# CLI
pip install "docstruct[cli]"

# Everything
pip install "docstruct[all]"
```

### Supported inputs and outputs

| Inputs | Outputs | Optional cloud |
|--------|---------|----------------|
| PDF (digital + scanned), PNG/JPEG/WebP/TIFF | JSON, NDJSON, XML, **Markdown** | **S3** read/write (`docstruct[s3]`) |
| **DOCX**, **PPTX** (native text, stdlib) | Provenance + validation telemetry | |

Native text path (no VLM): `client.extract_native("file.docx")` returns pages + markdown.

Also installs the `docstruct` command (same as `python -m docstruct`).

---

## Core Design Principles

1. **Model & Runtime Agnostic** - Ollama, OpenAI-compatible servers, PaddleOCR-VL, Docling, MinerU, and cloud VLMs all implement one uniform contract.
2. **Schema-First & Deterministic** - Never trust raw LLM text. Enforce contracts with Pydantic v2 / JSON Schema and custom business rules. Targeted repair + automatic escalation on failure.
3. **First-Class XML & JSON** - Deterministic JSON, streaming NDJSON, and configurable XML (namespaces, attributes vs elements, CDATA, optional XSD).
4. **Provenance & Telemetry** - Page numbers, bounding boxes, confidence, latency, estimated cost, and full validation reports on every result.
5. **Clean Core** - Minimal dependencies. Vendor quirks stay inside provider adapters.

---

## Enterprise Use Cases

### Use Case 1: Local Open-Weight VLM (Ollama) - Privacy First

```python
from docstruct import DocumentClient, OllamaProvider, RoutingPolicy
from pydantic import BaseModel, Field

class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float

class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total: float
    currency: str = "USD"
    lines: list[LineItem] = []

client = DocumentClient(
    providers=[
        OllamaProvider(model="qwen2.5vl:7b", base_url="http://localhost:11434"),
    ],
    default_routing=RoutingPolicy(primary_provider="ollama"),
)

result = client.extract("scanned_invoice.pdf", schema=Invoice)
print(result.to_json(include_telemetry=True))
```

### Use Case 2: Local-First with Cloud Fallback

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

### Use Case 3: Custom Business Validation Rules

```python
from docstruct.models.ir import DocumentIR
from pydantic import BaseModel

def check_line_items_sum_to_total(data: BaseModel, ir: DocumentIR) -> list[str]:
    """Return a list of error messages (empty = pass)."""
    if not hasattr(data, "lines") or not hasattr(data, "total"):
        return []
    calculated = sum(line.amount for line in data.lines)
    if abs(calculated - data.total) > 0.01:
        return [f"Line items sum ({calculated}) does not equal total ({data.total})"]
    return []

result = client.extract(
    "invoice.pdf",
    schema=Invoice,
    rules=[check_line_items_sum_to_total],
)

if not result.validation.is_valid:
    print("Validation failed:", result.validation.errors)
```

### Use Case 4: XML Export with Namespaces & Attributes

```python
xml = result.to_xml(
    root_tag="Invoice",
    list_item_tags={"lines": "Line"},
    attribute_fields={"currency", "invoice_number"},
    namespaces={"inv": "http://example.com/invoice/v1"},
    pretty=True,
)
print(xml)
```

### Use Case 5: Streaming NDJSON for Lakehouse / RAG

```python
from docstruct.serializers import to_ndjson

results = [client.extract(f) for f in pdf_files]
ndjson_stream = to_ndjson(results, include_telemetry=False)

with open("invoices.ndjson", "w", encoding="utf-8") as f:
    f.write(ndjson_stream)
```

### Use Case 6: Generic HTTP OCR Service (Docling / MinerU / PaddleOCR-VL)

```python
from docstruct import DocumentClient, HttpOCRProvider, RoutingPolicy

client = DocumentClient(
    providers=[
        HttpOCRProvider(
            endpoint="http://localhost:8000/extract",
            name="docling",
        ),
    ],
    default_routing=RoutingPolicy(primary_provider="docling"),
)
```

### Use Case 7: CLI

```bash
# JSON with telemetry
docstruct extract invoice.pdf --schema schema.json --format json -o out.json

# XML
docstruct extract invoice.pdf --format xml --root-tag Invoice -o out.xml

# Using Ollama
docstruct extract scan.png --provider ollama --format json
```

---

## Architecture Overview

```
docstruct/
├── client.py              # DocumentClient – public entry point
├── config.py              # RoutingPolicy
├── models/
│   ├── ir.py              # DocumentIR, PageIR, Block, BBox
│   ├── result.py          # ExtractionResult, Telemetry, ValidationReport
│   └── schema.py          # Pydantic / JSON Schema normalization
├── providers/
│   ├── base.py            # BaseOCRProvider + ProviderCapabilities
│   ├── mock.py            # Deterministic test double
│   ├── ollama.py          # Local Ollama VLM
│   ├── openai_compat.py   # vLLM, LM Studio, OpenAI, Azure…
│   └── http_ocr.py        # Generic REST adapter
├── pipeline/
│   ├── ingest.py          # PDF / image → PageInput
│   ├── router.py          # Routing, retry, escalation
│   ├── validator.py       # Schema + business rules
│   └── telemetry.py       # Cost & latency helpers
└── serializers/
    ├── json_serializer.py # to_json / to_dict / to_ndjson
    └── xml_serializer.py  # to_xml (namespaces, attributes, XSD)
```

---

## Intermediate Representation (IR)

All providers produce a vendor-neutral IR before schema validation:

| Model | Key Fields |
|---|---|
| **BBox** | `x0, y0, x1, y1`, `coordinate_space` (`normalized` \| `pixel`), `page_number` |
| **Block** | `block_id`, `kind` (text/heading/table/key_value/…), `content`, `bbox`, `confidence` |
| **PageIR** | `page_number`, `width`, `height`, `blocks`, `raw_text` |
| **DocumentIR** | `source_name`, `page_count`, `pages`, `raw_markdown`, `provider_metadata` |

---

## Provider Capabilities Matrix

| Provider | Structured JSON | BBoxes | PDF Native | Max Pages / Call | Typical Use |
|---|---|---|---|---|---|
| **MockProvider** | ✅ | ✅ |   | 50 | Tests, demos |
| **OllamaProvider** | ✅ |   |   | 4 | Local privacy |
| **OpenAICompatProvider** | ✅ |   |   | 8 | GPT-4o, vLLM, Claude-compatible |
| **HttpOCRProvider** | ✅ | ✅ | Configurable | Configurable | Docling, MinerU, PaddleOCR-VL |

---

## Error Handling & Validation

```python
from docstruct import ValidationError, ProviderError

try:
    result = client.extract("bad.pdf", schema=Invoice)
except ValidationError as e:
    print(e.errors)      # list of human-readable messages
    print(e.attempts)    # how many tries were made
except ProviderError as e:
    print(e.provider, e.status_code)
```

Validation is **never silent**. Every `ExtractionResult` carries a `ValidationReport`:

```python
result.validation.is_valid   # bool
result.validation.errors     # list[str]
result.validation.attempts   # int
result.validation.rules_failed
```

---

## Testing

```bash
pip install "docstruct[dev]"
pytest tests/ -q
```

The suite covers MockProvider single/multi-page runs, retry & fallback escalation, JSON/NDJSON/XML edge cases (attributes, namespaces, escaping), and HTTP error handling.

---

## License

MIT License. See [LICENSE](LICENSE).

---

**Documentation site:** [https://thekakodkar.github.io/docstruct/](https://thekakodkar.github.io/docstruct/)  
**Repository:** [https://github.com/thekakodkar/docstruct](https://github.com/thekakodkar/docstruct)
