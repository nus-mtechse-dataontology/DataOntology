# DataOntology Project Audit Report

## Tech Stack
- Language: Python 3.14 (declared in `pyproject.toml`)
- Web/API: FastAPI, Uvicorn, Starlette (`pyproject.toml`, `requirements.txt`)
- Data modeling: Pydantic, SQLModel, SQLAlchemy (`pyproject.toml`, `requirements.txt`)
- LLM integration: Google Gemini gateway (and OpenAI gateway present) (`src/llm_gateway/providers/gemini_gateway.py`, `src/llm_gateway/providers/openai_gateway.py`)
- CLI tooling: Typer (`src/batch_main.py`)
- Config: `python-dotenv`, `tomllib` + `resources/config.toml` (`src/lifecycle_hooks/startup.py`, `resources/config.toml`)
- Testing: pytest, pytest-cov (`pyproject.toml`, `requirements.txt`)

## Architecture
- Pattern: Monolithic service with a layered NLQ pipeline and explicit orchestration. FastAPI routes delegate to a single Orchestrator that coordinates prompt building, LLM call, syntactic/semantic validation, SQL compilation, execution, and response formatting.
- Entry points:
  - HTTP server: `src/main.py` (FastAPI app, middleware, routers, startup lifespan).
  - CLI ingestion: `src/batch_main.py` (Typer app driving ingestion and table creation).
- Runtime wiring happens in `src/lifecycle_hooks/startup.py`, which loads config and semantic model, initializes pipeline components, and attaches the Orchestrator to `app.state`.

## Ontology Logic
- No RDF/OWL/Turtle/NT/NQ files found.
- Ontology semantics live in JSON:
  - SQL semantic layer with intents and SQL templates: `src/ontology/semantic_layer.json`
  - LLM-facing semantic layer without SQL: `src/ontology/semantic_layer_llm.json`
- Loader + cache: `src/ontology/semantic_model_loader.py`

## Ingestion Summary
- Entry points:
  - CLI: `src/batch_main.py` with `--ingestion-type` and `--project-path`
  - HTTP: `POST /ingestion/upload` (manual ingestion) in `src/endpoints/routes/ingestion/ingestion_routes.py`
- Modes:
  - API ingestion: `src/ingestion/source/api_source/*` via `ApiEntry` + `ApiGateway`
  - File ingestion: `src/ingestion/source/file_source/file_ingestion.py` via `FileEntry`
  - Manual ingestion: `src/ingestion/source/manual_source/manual_ingestion.py`
- Configuration:
  - Dataset configs in `datasets/*.yml` define source, DB target, and module wiring.
  - Vault secrets used for API and DB credentials in `vault/` (e.g., `destination.apiKey`, `postgres.user`).
- Typical CLI usage:
  - `uv run src/batch_main.py --ingestion-type="airport" --project-path="$(pwd)"`
  - Convenience scripts in `bin/` mirror these commands (e.g., `bin/airport.sh`, `bin/city.sh`).
- Behavior:
  - API ingestion prepares a signed request, calls the upstream API, and writes results through DAO + service classes.
  - File ingestion reads CSV from a `file:///` URI and bulk inserts into the configured table.
  - Manual ingestion inserts provided rows into a target table; schema listing is available at `GET /ingestion/get_schema`.

## Key Files (core logic)
1. `src/main.py` — app entry point and router wiring.
2. `src/lifecycle_hooks/startup.py` — dependency wiring and pipeline assembly.
3. `src/orchestrator/orchestrator.py` — NLQ pipeline control flow.
4. `src/compiler/sql_compiler.py` — query plan to SQL translation.
5. `src/ontology/semantic_layer.json` — semantic model (intents, params, SQL templates).

## Next Steps
1. Validate and version the semantic model schema. Add JSON Schema validation and explicit version migration logic for `semantic_layer.json`.
2. Add deterministic tests for each intent → SQL template mapping, including parameter coercion and boundary cases.
3. Consider separating ingestion and query-serving concerns into distinct modules or processes for clearer operational boundaries and deployment.
