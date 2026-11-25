"""
docstruct Playground - test extraction against real PDFs and images.

Run:
    pip install "docstruct[pdf]" streamlit
    streamlit run examples/playground.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Allow running without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st
from pydantic import BaseModel, create_model

from docstruct import (
    DocumentClient,
    MockProvider,
    OllamaProvider,
    OpenAICompatProvider,
    RoutingPolicy,
    ValidationError,
    ProviderError,
)


st.set_page_config(
    page_title="docstruct Playground",
    page_icon="📄",
    layout="wide",
)

st.title("docstruct Playground")
st.caption("Upload a PDF or image, pick a provider, extract structured JSON or XML.")

with st.sidebar:
    st.header("Provider")
    provider_name = st.selectbox(
        "Backend",
        ["mock", "ollama", "openai_compat"],
        help="mock = offline demo data. ollama = local VLM. openai_compat = cloud or vLLM.",
    )

    ollama_model = "qwen2.5vl:7b"
    ollama_base = "http://localhost:11434"
    openai_model = "gpt-4o"
    openai_base = "https://api.openai.com/v1"
    openai_key = ""

    if provider_name == "ollama":
        ollama_model = st.text_input("Ollama model", ollama_model)
        ollama_base = st.text_input("Ollama base URL", ollama_base)
    elif provider_name == "openai_compat":
        openai_model = st.text_input("Model", openai_model)
        openai_base = st.text_input("Base URL", openai_base)
        openai_key = st.text_input("API key", type="password")

    st.header("Output")
    out_format = st.radio("Format", ["json", "xml"], horizontal=True)
    include_telemetry = st.checkbox("Include telemetry", value=True)
    root_tag = st.text_input("XML root tag", "Document")

    st.header("Schema (optional)")
    schema_mode = st.radio(
        "Schema source",
        ["None (free form)", "Built-in Invoice", "JSON Schema paste"],
    )
    schema_json_text = ""
    if schema_mode == "JSON Schema paste":
        schema_json_text = st.text_area(
            "JSON Schema",
            height=180,
            placeholder='{"type":"object","properties":{"vendor":{"type":"string"}},"required":["vendor"]}',
        )

    st.header("Prompt")
    prompt_hint = st.text_area(
        "Extraction hint",
        "Extract all key fields from this document as structured JSON.",
        height=80,
    )


class LineItem(BaseModel):
    description: str = ""
    qty: float = 0.0
    unit_price: float = 0.0
    amount: float = 0.0


class Invoice(BaseModel):
    vendor: str = ""
    invoice_number: str = ""
    total: float = 0.0
    currency: str = "USD"
    lines: list[LineItem] = []


def build_schema():
    if schema_mode == "Built-in Invoice":
        return Invoice
    if schema_mode == "JSON Schema paste" and schema_json_text.strip():
        try:
            data = json.loads(schema_json_text)
            props = data.get("properties", {})
            required = set(data.get("required", []))
            fields = {}
            type_map = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            for name, prop in props.items():
                py = type_map.get(prop.get("type", "string"), str)
                default = ... if name in required else None
                fields[name] = (py, default)
            return create_model("DynamicSchema", **fields)
        except Exception as exc:
            st.sidebar.error(f"Invalid JSON Schema: {exc}")
            return None
    return None


uploaded = st.file_uploader(
    "PDF or image",
    type=["pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff"],
)

col_run, col_info = st.columns([1, 3])
with col_run:
    run = st.button("Extract", type="primary", use_container_width=True)

if run:
    if not uploaded:
        st.warning("Upload a PDF or image first.")
        st.stop()

    suffix = Path(uploaded.name).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name

    providers = []
    if provider_name == "mock":
        providers.append(MockProvider())
    elif provider_name == "ollama":
        providers.append(OllamaProvider(model=ollama_model, base_url=ollama_base))
    else:
        providers.append(
            OpenAICompatProvider(
                model=openai_model,
                base_url=openai_base,
                api_key=openai_key or None,
            )
        )

    client = DocumentClient(
        providers=providers,
        default_routing=RoutingPolicy(primary_provider=providers[0].name),
    )
    schema = build_schema()

    try:
        with st.spinner("Extracting..."):
            result = client.extract(
                tmp_path,
                schema=schema,
                prompt_hint=prompt_hint,
            )
    except ValidationError as e:
        st.error("Validation failed after retries")
        st.write(e.errors)
        st.stop()
    except ProviderError as e:
        st.error(f"Provider error ({e.provider}): {e}")
        st.stop()
    except Exception as e:
        st.exception(e)
        st.stop()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    st.success(
        f"Valid={result.validation.is_valid} | "
        f"Providers={result.telemetry.providers_used} | "
        f"Latency={result.telemetry.total_latency_ms:.0f} ms"
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Structured data")
        if out_format == "json":
            text = result.to_json(indent=2, include_telemetry=include_telemetry)
            st.code(text, language="json")
            st.download_button("Download JSON", text, file_name="extraction.json")
        else:
            text = result.to_xml(root_tag=root_tag, pretty=True)
            st.code(text, language="xml")
            st.download_button("Download XML", text, file_name="extraction.xml")

    with right:
        st.subheader("Validation")
        st.json(result.validation.model_dump())
        st.subheader("Telemetry")
        st.json(result.telemetry.model_dump())

else:
    st.info(
        "Upload a document and click **Extract**. "
        "Use **mock** for an offline demo without any model server."
    )
