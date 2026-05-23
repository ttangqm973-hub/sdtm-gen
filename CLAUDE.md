# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDTM GEN is a Python-based SDTM (Study Data Tabulation Model) SAS code generator for clinical trial data. It reads SPEC Excel/CSV files and generates CDISC SDTM-compliant SAS programs, including SUPPXX (Supplemental Qualifiers). Includes a RAG pipeline for AI-assisted derivation of complex variables.

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
# All tests — run with python -m pytest on Windows
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_rag.py -v
python -m pytest tests/test_web_api.py -v

# Single test method
python -m pytest tests/test_rag.py::TestMockGenerator::test_generate_conditional_zh -v
```

### CLI Commands

```bash
# Generate SAS from single domain SPEC
sdtm-gen generate spec.xlsx -o output_dir

# Batch generate all domains (with lint + RAG mock)
sdtm-gen batch spec.xlsx -o output_dir --study-name STUDY001 --rag --rag-mock --lint -v

# Analyze SPEC file structure
sdtm-gen analyze spec.xlsx -v

# Lint generated SAS
sdtm-gen lint output/ae.sas --json

# Build/rebuild knowledge base
sdtm-gen build-kb --mock --force

# Add single file to knowledge base (incremental)
sdtm-gen kb-add path/to/file.xlsx --mock -v

# Also works as module: python cli.py <command> ...
```

### Web Server

```bash
pip install -e .
python -m uvicorn web.app:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080` in browser. Static files from `web/static/` are auto-mounted at root.
**Important:** When JS/HTML is updated, add cache-busting `?v=N` to script/style tags in `index.html` — users must Ctrl+F5 refresh to clear cached scripts.

## Architecture

### Core Pipeline

```text
SPEC Excel/CSV → parser/excel_reader.py → parser/ir_builder.py → generator/sas_generator.py → .sas file
                     ↓                            ↓
              column_mapper.py            ir/models.py (DomainIR, Variable, SuppQualifier)
                                          parser/source_algorithm_parser.py
```

- **Parser layer**: `excel_reader.py` reads multi-sheet Excel/CSV with auto header detection (`_find_header_row`). `column_mapper.py` maps column names via `config.py`'s `SPEC_COLUMN_ALIASES`. `ir_builder.py` constructs `DomainIR`, routes variables to `template` vs `ai_required`, and now calls `source_algorithm_parser.py` to extract structured mappings from the `Source/Algorithm` column.
- **Source/Algorithm Engine** (`parser/source_algorithm_parser.py`): Parses the `Source/Algorithm` column into `ParsedAlgorithm` dataclass with 12 patterns: `direct_assign`, `conditional`, `raw_mapping`, `sdtm_ref`, `cross_ref`, `raw_dataset_ref`, `raw_domain`, `substring_raw`, `substring`, `external`, `reference`, `date_calculation`, `complex`. The `is_templateable` flag drives code generation routing.
- **IR layer**: `ir/models.py` defines `Variable` (source_algorithm, raw_source, sub_part, direct_value fields added), `DomainIR` (supp_qualifiers field), and `SuppQualifier` (qnam, qlabel, origin, source_algorithm, raw_source, sub_part, direct_value).
- **Generator layer**: `template_renderer.py` passes `supp_qualifiers` to Jinja2 context. Falls back to `generic_sdtm.sas.j2` when a domain-specific template (e.g., `be_sdtm.sas.j2`) is not found. `sas_generator.py` orchestrates output file generation.
- **Lint layer**: `sas_lexer.py` tokenizes SAS; `sas_parser.py` checks structural integrity; `sas_linter.py` reports issues.

### SUPPXX Association

SUPP (Supplemental Qualifiers) datasets are auto-associated with their parent domain:

1. `config.py` defines `SUPP_PARENT_MAP` / `PARENT_SUPP_MAP` bidirectional mapping (e.g., SUPPAE ↔ AE).
2. `BatchScheduler._load_supp_qualifiers()` scans the spec file's directory for paired `SUPPxx.xlsx` files, reads their `Values` sheet, and parses each qualifier into a `SuppQualifier`. Uses flexible column matching (`_get_col` helper with prefix lookup) to handle column name variants like `QNAM(IDVAR)` vs `QNAM`.
3. Qualifiers are attached to `DomainIR.supp_qualifiers` before template rendering.
4. Templates (`ae_sdtm.sas.j2`, `dm_sdtm.sas.j2`, `generic_sdtm.sas.j2`) generate a SUPP data step when `{% if supp_qualifiers %}` is non-empty. Qualifiers with `raw_source` produce direct `if strip(_VAR) ne ""` mappings; those with `sub_part` produce substring extraction; those with `direct_value` produce constant assignments; others produce `[AI-GEN-START]` markers.

**Critical**: For SUPP files to be found, they must be in the **same directory** as the parent SPEC file. In the Web API, this means uploading the parent and SUPP files together in a single multi-file upload.

### Domain Detection

`BatchScheduler._resolve_domain(sheet_name, spec_file)` determines the actual SDTM domain:

1. If sheet_name is a known SDTM domain → use it.
2. If filename is a known SDTM domain → use it.
3. If filename_clean (strip `_spec` suffix) is known → use it.
4. **Fallback**: return filename_clean (not sheet_name). This handles files like `BE.xlsx` where the sheet is named "Variable" and "BE" isn't in the standard domain list.

### RAG Pipeline

```text
Knowledge base (SAS code / macros / SPEC templates / SDTM IG PDF)
    → rag/knowledge_processor.py → KnowledgeChunks
    → rag/embedder.py → rag/vector_store.py (ChromaDB or SimpleVectorStore fallback)
    → rag/retriever.py → rag/generator.py (CodeGenerator or MockGenerator)
    → rag/integrator.py (processes DomainIR ai_required variables)
    → AI-generated SAS code injected into templates
```

- **Incremental add**: `RAGPipeline.add_to_knowledge_base(file_path)` parses a single file and adds chunks without deleting existing data. Auto-detects file type by extension (.sas, .txt, .xlsx, .pdf). Exposed via CLI `kb-add` and Web API `POST /api/kb/upload`.
- **SpecParser** in `knowledge_processor.py` now ingests variables with `Source/Algorithm` content (not just `Algorithm for Programming`).
- **MockGenerator**: 10 derivation templates; works without API keys. **CodeGenerator**: Real LLM via Anthropic API with exponential backoff retry.

### Web API

- **Multi-file upload**: `POST /api/upload` accepts `list[UploadFile]`. All files saved to one directory so `_load_supp_qualifiers` can find SUPP pairs.
- **Background jobs**: Use `threading.Thread` (not `asyncio.create_task`) because FastAPI's `TestClient` does not reliably execute asyncio background tasks. The scheduler runs synchronously in a daemon thread; status polled via `/api/status/{job_id}`.
- **Route ordering**: `/api/download/{job_id}/all` must be registered BEFORE `/api/download/{job_id}/{domain}` — FastAPI matches greedily.
- **Domain filter**: `upload` endpoint filters out domains starting with "SUPP" from `domains_detected` — SUPP domains are auto-associated, not selectable.

### Template Conventions

- Templates live in `templates/sas/`. Naming: `{domain}_sdtm.sas.j2` (lowercase domain).
- `domain_header.sas.j2` is the shared header with macro definitions.
- `generic_sdtm.sas.j2` is the fallback for domains without a dedicated template (e.g., BE, PC, custom domains).
- `suppxx_sdtm.sas.j2` exists but is not the primary SUPP path — SUPP generation is done inline in each domain's template via `{% if supp_qualifiers %}`.

## Important Conventions

- **Variable generation routing**: `ir_builder.py` assigns `generation="ai_required"` when `origin == "Derived"` AND `algorithm` is non-empty. All others get `generation="template"`.
- **AI code markers**: Generated SAS files wrap AI-generated code in `/* [AI-GEN-START] domain=X variable=Y confidence=Z */` ... `/* [AI-GEN-END] */` markers.
- **Knowledge base path**: Hardcoded default is `D:/Claude code/Knowlegde base`. Override with `--kb-path` CLI flag or `kb_path` in Web API request.
- **SUPP column flexibility**: Values sheet columns may vary — `QNAM` vs `QNAM(IDVAR)`, `Result Variable` vs `Result_variable`. Always use prefix-matching lookups.
- **Date handling**: ISO 8601 DTC variables: `input(strip(scan(DTCVAR, 1, 'T')), ??yymmdd10.)`. Study day: `date - RFSTDT + 1`.
- **CLI entry**: `cli.py` is both a module (`python cli.py`) and an installed script (`sdtm-gen`) via `setup.py` `entry_points`. Test both paths after editing.
- **Empty domain handling**: If `domains_to_process` is empty, set `job.status = "failed"` with a descriptive error, not `"success"`.
- **Browser cache on frontend changes**: Update `?v=N` query strings on JS/CSS links in `index.html` and instruct users to Ctrl+F5 refresh.
- **`.env` / secrets**: Never commit API keys. Template in `.env.example`.
