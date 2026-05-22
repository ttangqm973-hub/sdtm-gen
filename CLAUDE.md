# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDTM GEN is a Python-based SDTM (Study Data Tabulation Model) SAS code generator for clinical trial data. It reads SPEC Excel/CSV files and generates CDISC SDTM-compliant SAS programs. The project includes a RAG (Retrieval-Augmented Generation) pipeline for AI-assisted derivation of complex variables.

**Primary language:** Python 3.10+  
**Secondary:** Jinja2 templates for SAS code generation

## Common Commands

### Setup

```bash
cd "d:/Claude code/sdtm_gen"
pip install -r requirements.txt
pip install -e .
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Single test file
pytest tests/test_rag.py -v

# Single test class
pytest tests/test_rag.py::TestMockGenerator -v

# Single test method
pytest tests/test_rag.py::TestMockGenerator::test_generate_conditional_zh -v

# Web API tests only
pytest tests/test_web_api.py -v

# Batch scheduler tests only
pytest tests/test_batch_scheduler.py -v
```

### CLI Commands

```bash
# Generate SAS from SPEC (template-only)
sdtm-gen generate spec.xlsx -o output_dir

# Generate with RAG mock (for testing AI variable generation without API keys)
sdtm-gen generate spec.xlsx -o output_dir --rag --rag-mock -v

# Generate with real LLM (requires ANTHROPIC_API_KEY)
sdtm-gen generate spec.xlsx -o output_dir --rag -v

# Batch generate all domains in a Study SPEC
sdtm-gen batch spec.xlsx -o output_dir --study-name STUDY001
sdtm-gen batch spec.xlsx --domains DM,AE,LB --rag --lint -v

# Analyze SPEC file
sdtm-gen analyze spec.xlsx -v

# Lint generated SAS
sdtm-gen lint output/ae.sas --json

# Build knowledge base
sdtm-gen build-kb --mock --force
```

### Web Server

```bash
# Start FastAPI dev server (requires package installed)
pip install -e .  # if not already installed
uvicorn web.app:app --host 0.0.0.0 --port 8080
```

Then open `http://localhost:8080` in browser. The static files from `web/static/` are auto-mounted at root.

## Architecture

### Core Pipeline (Phase 1)

```text
SPEC Excel/CSV → parser/excel_reader.py → parser/ir_builder.py → generator/sas_generator.py → .sas file
                                    ↓
                              ir/models.py (DomainIR, Variable)
```

- **Parser layer**: `excel_reader.py` reads multi-sheet Excel/CSV; `column_mapper.py` maps column names via `config.py`'s `SPEC_COLUMN_ALIASES`; `ir_builder.py` constructs `DomainIR` with variable generation routing (`template` vs `ai_required`).
- **IR layer**: `ir/models.py` defines `Variable` (seq, name, label, type, length, origin, generation, codelist, algorithm, ai_context) and `DomainIR` (domain, variables, primary_key, macro_refs, ai_summary).
- **Generator layer**: `template_renderer.py` initializes Jinja2 environment from `templates/sas/`; `sas_generator.py` orchestrates output file generation. Templates include `domain_header.sas.j2` (shared header macros) and per-domain templates (ae_sdtm.sas.j2, dm_sdtm.sas.j2, etc.).
- **Lint layer**: `sas_lexer.py` tokenizes SAS code; `sas_parser.py` checks structural integrity (unclosed DATA/PROC steps, unbalanced DO/END); `sas_linter.py` reports issues.

### RAG Pipeline (Phase 2)

```text
Knowledge base (SAS code / macros / SPEC templates / SDTM IG PDF)
    → rag/knowledge_processor.py → KnowledgeChunks
    → rag/embedder.py (OpenAI / local / mock)
    → rag/vector_store.py (ChromaDB or SimpleVectorStore fallback)
    → rag/retriever.py (hybrid: semantic + keyword + metadata filter)
    → rag/generator.py (CodeGenerator with Claude API, or MockGenerator with templates)
    → rag/integrator.py (RAGIntegrator processes DomainIR ai_required variables)
    → AI-generated SAS code injected into templates
```

- **MockGenerator**: Template-driven fallback when no API key is available. Contains 10 derivation templates: `iso_date_parse`, `conditional_assignment`, `flag_derivation`, `categorical_mapping`, `numeric_computation`, `study_day`, `baseline_flag`, `first_last_by_group`, `cross_domain_lookup`, plus `fallback`.
- **CodeGenerator**: Real LLM integration via Anthropic API. Features: system prompt, exponential backoff retry (3 attempts), token-safe prompt truncation (chunks ≤300 chars), multi-format code extraction (```sas/SAS/saslog/untagged), configurable model via `CLAI_MODEL` env var.
- **RAGIntegrator**: Connects IR Builder to RAG Pipeline. For each `ai_required` variable, calls `generate_with_report()`, attaches `ai_generated_code` / `ai_confidence` / `ai_sources` / `ai_warnings` back to the Variable, then exports `domain_ai_report.json`.

### Batch & Web Pipeline (Phase 3)

**Batch Scheduler** (`batch/scheduler.py`):

- Orchestrates multi-domain generation from a single SPEC file.
- Uses `StudyConfig` (`batch/study_config.py`) for study-level settings: domain whitelist, global macro refs, RAG/Lint toggles.
- Concurrent domain processing via `ThreadPoolExecutor` (default 4 workers). Single-domain runs skip the thread pool.
- Outputs `batch_report.json` with per-domain status, elapsed time, lint issues.

**Web API** (`web/api.py`, `web/app.py`):

- FastAPI application with CORS and optional static file serving (for the web UI in `web/static/`).
- In-memory stores for uploads, jobs, history, and SSE queues. No persistence layer yet.
- **Critical implementation detail**: Background jobs use `threading.Thread` (not `asyncio.create_task`) because FastAPI's `TestClient` does not reliably execute asyncio background tasks to completion between requests. The scheduler runs synchronously in a daemon thread; status is polled via `/api/status/{job_id}`.
- **Route ordering gotcha**: `/api/download/{job_id}/all` must be registered BEFORE `/api/download/{job_id}/{domain}` in the router. FastAPI matches path parameters greedily; `/all` would otherwise be captured as `domain="all"`.

### SPEC Template Format

Real-world SPEC templates (in `D:/Claude code/Knowlegde base/SPEC template/`) use this structure:

- **Multi-sheet xlsx**: `Variable`, `Values`, `Codelist`
- **Variable sheet**: First 5-6 rows are metadata (dataset description, structure, key variables, sort order). The actual header row is around row 6-7 with columns: `VarOrd`, `VarName`, `VarLabel`, `VarType`, `VarLen`, `VarFormat`, `CT/CodeListID`, `Core`, `Origin`, `Source/Algorithm`, `CRF Pages`, `Algorithm for Programming`.
- `ExcelReader._find_header_row()` automatically scans for the header row by matching indicator keywords (`varname`, `vartype`, `origin`, etc.). It does NOT assume row 0 is the header.

### Key Configuration Files

- `config.py`: SPEC column mappings (`SPEC_COLUMN_MAP`, `SPEC_COLUMN_ALIASES`), domain labels, macro library categories, SAS keywords, variable classes.
- `requirements.txt`: Core deps (openpyxl, pydantic, Jinja2, click, pytest) + RAG deps (anthropic, openai, chromadb, sentence-transformers, PyPDF2, tenacity, python-dotenv) + Web deps (fastapi, uvicorn, python-multipart).
- `.env.example`: Template for `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CLAI_MODEL`.

### Testing Strategy

- **Unit tests** (`tests/test_*.py`): Individual component testing. MockEmbedder and MockGenerator are fully unit-testable without API keys.
- **E2E tests** (`tests/test_e2e.py`): Full pipeline using real SPEC templates from `D:/Claude code/Knowlegde base/SPEC template/`. Requires knowledge base files on disk.
- **RAG tests**: All RAG tests default to `use_mock_llm=True` so they run without API keys in CI. To test real LLM integration, set `ANTHROPIC_API_KEY` and use `use_mock_llm=False`.
- **Web API tests** (`tests/test_web_api.py`): Integration tests using FastAPI `TestClient`. Tests upload → generate → status polling → download. Status polling uses `time.sleep()` loops because background jobs run in independent threads.

## Important Conventions

- **Variable generation routing**: `ir_builder.py` assigns `generation="ai_required"` when `origin == "Derived"` AND `algorithm` is non-empty. All others get `generation="template"`.
- **AI code markers**: Generated SAS files wrap AI-generated code in `/* [AI-GEN-START] domain=X variable=Y confidence=Z */` ... `/* [AI-GEN-END] */` markers.
- **Knowledge base path**: Hardcoded default is `D:/Claude code/Knowlegde base` (note the typo in "Knowlegde"). Override with `--kb-path` CLI flag or `kb_path` in Web API request.
- **Cross-domain references**: When a variable's algorithm mentions `sdtm.XX.VARNAME` or `related_domains` is populated, the `cross_domain_lookup` template triggers, generating PROC SORT + MERGE by USUBJID.
- **Date handling**: ISO 8601 DTC variables are parsed with `input(strip(scan(DTCVAR, 1, 'T')), ??yymmdd10.)`. Study day variables calculate `date - RFSTDT + 1`.
- **Domain detection in Web API**: The `upload` endpoint must call `BatchScheduler._resolve_domain()` to map sheet names (e.g., `Variable`) to actual SDTM domain names (e.g., `AE`), NOT return raw sheet names. If `config.domains` contains sheet names while `_resolve_domain` returns real domains, the domain filter in `BatchScheduler.run` will skip everything and produce empty results.
- **Empty domain handling**: If `domains_to_process` is empty (no valid variable sheets detected), `_run_job_sync` sets `job.status = "failed"` with a descriptive error, rather than incorrectly marking it as `success`.
- **CLI entry**: `cli.py` is both a module (`python cli.py`) and an installed script (`sdtm-gen`) via `setup.py` `entry_points`. When editing CLI commands, verify both paths work.
