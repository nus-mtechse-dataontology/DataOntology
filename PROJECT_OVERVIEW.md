# DataOntology — Project Overview

## What It Is

A **Natural Language Query (NLQ) → SQL pipeline** for flight data. Users ask plain English questions (e.g., "What's the cheapest flight from Singapore to Bangkok next week?") and get structured answers. Built as an NUS Software Engineering Master's project.

---

## Architecture: 7-Stage Explicit Pipeline

```
NLQRequest
  [1] PromptBuilder    → PromptBundle (Jinja2 + semantic model)
  [2] LLMGateway       → LLMRawResponse (Gemini or OpenAI)
  [3] SyntacticValidator → QueryPlan (parse JSON, validate schema)
  [4] SemanticValidator → QueryPlan (intent exists, params present)
  [5] SQLCompiler      → CompiledSQL (parameterized SQL from template)
  [6] SQLExecutor      → ResultSet (execute via DAO)
  [7] ResponseBuilder  → QuestionResponse (formatted answer)
```

Each stage has typed Pydantic I/O. Any error short-circuits the pipeline immediately.

---

## Project Structure

```
/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml                     # Python 3.14+, dependencies
├── requirements.txt
├── uv.lock
├── Dockerfile                         # Multi-stage Lambda runtime
├── template.yaml                      # AWS SAM CloudFormation template
├── samconfig.toml                     # SAM deploy config
├── DataOntology.drawio               # Architecture diagram
│
├── src/
│   ├── main.py                        # FastAPI app entry point
│   ├── batch_main.py                  # Typer CLI for data ingestion
│   ├── lifecycle_hooks/
│   │   └── startup.py                 # Dependency injection & wiring
│   ├── endpoints/routes/
│   │   ├── query/query_routes.py      # POST /query/query
│   │   ├── telegram/telegram_routes.py
│   │   ├── auth/auth_routes.py
│   │   ├── status/status_routes.py
│   │   ├── register/register_routes.py
│   │   └── ingestion/ingestion_routes.py
│   ├── orchestrator/
│   │   ├── orchestrator.py            # 7-stage pipeline runner
│   │   ├── response_builder.py
│   │   └── error_response_builder.py
│   ├── prompt_builder/
│   │   ├── prompt_builder.py
│   │   └── templates/query_plan_prompt.j2
│   ├── llm_gateway/
│   │   ├── llm_gateway.py             # Abstract LLM interface
│   │   ├── gateway_factory.py
│   │   ├── gateway_registry.py
│   │   ├── parser/raw_response.py     # Markdown fence stripper
│   │   └── providers/
│   │       ├── gemini_gateway.py
│   │       └── openai_gateway.py
│   ├── validators/
│   │   ├── syntactic/syntactic_validator.py  # JSON parse + schema check
│   │   └── semantic/semantic_validator.py    # Intent + param validation
│   ├── compiler/
│   │   └── sql_compiler.py            # QueryPlan → parameterized SQL
│   ├── execution/
│   │   └── sql_executor.py            # SQL execution via DAO
│   ├── ontology/
│   │   ├── semantic_layer_v2.json     # SOURCE OF TRUTH: intents, SQL templates, param schemas
│   │   ├── semantic_layer_llm.json    # LLM-facing semantic model
│   │   └── semantic_model_loader.py
│   ├── models/
│   │   ├── pipeline.py                # NLQRequest, QueryPlan, CompiledSQL, etc.
│   │   ├── common.py                  # SuccessResponse, ErrorResponse
│   │   ├── app_model.py
│   │   ├── admin_model.py
│   │   └── ingestion_model.py
│   ├── entities/                      # SQLModel ORM (star schema)
│   │   ├── fact_flight_info.py
│   │   ├── airport.py, city.py, country.py
│   │   ├── airline.py, aircraft.py, currency_rate.py
│   │   └── accounts.py, airline_coverage.py
│   ├── dao/                           # Data Access Objects
│   │   ├── base_dao.py
│   │   ├── fact_flight_info_dao.py
│   │   └── [dimension DAOs]
│   ├── ingestion/
│   │   ├── entry/                     # FileEntry, ApiEntry
│   │   ├── source/                    # api_source/, file_source/, manual_source/
│   │   ├── services/                  # Per-entity business logic
│   │   └── gateway/api_gateway.py     # Upstream API calls
│   ├── services/
│   │   ├── auth/jwt_handler.py
│   │   ├── auth/authentication_service.py
│   │   └── registration/registration_service.py
│   ├── adapters/
│   │   └── telegram/
│   │       ├── client.py
│   │       ├── mapper.py
│   │       └── webhook_handler.py
│   ├── session/db_session.py
│   ├── configurations/               # Config loading (app, admin, logger)
│   ├── drivers/postgres_driver.py
│   └── dependencies/, factory/, handlers/
│
├── tests/
│   ├── conftest.py
│   ├── unit/                          # Fast, mocked component tests
│   ├── integration/                   # Multi-component + seam tests
│   └── e2e/
│       ├── test_golden_questions.py   # Regression suite (6 known Q&A pairs)
│       └── test_orchestrator_with_real_llm.py
│
├── docs/
│   ├── README.md
│   ├── CLAUDE.md                      # Audit report
│   └── testing.md
│
├── resources/
│   ├── config.toml                    # Runtime config (LLM, DB, JWT, service)
│   ├── flights.db                     # SQLite database (local dev)
│   └── seed_local.sql
│
├── datasets/                          # Ingestion YAML configs (7 files)
│   ├── fact_flight_info.yml
│   ├── airport.yml, city.yml, airline.yml, ...
│
├── vault/                             # Secrets (vault pattern)
│   ├── postgres.user
│   └── postgres.password
│
├── bin/                               # Convenience shell scripts
├── templates/config.toml              # Config template with placeholders
├── .github/workflows/ontology-ci.yaml # CI/CD pipeline
└── .zap/rules.tsv                     # OWASP ZAP security rules
```

---

## Key Components

| Component | Path | Role |
|-----------|------|------|
| Orchestrator | `src/orchestrator/orchestrator.py` | Wires and runs all 7 stages |
| Semantic Model | `src/ontology/semantic_layer_v2.json` | **Source of truth** — intents, SQL templates, param schemas |
| LLM Gateway | `src/llm_gateway/` | Pluggable Gemini / OpenAI via registry pattern |
| SQL Compiler | `src/compiler/sql_compiler.py` | Maps intent → parameterized SQL |
| Startup / DI | `src/lifecycle_hooks/startup.py` | Wires all dependencies into `app.state` |
| Ingestion CLI | `src/batch_main.py` | Typer CLI for loading API/CSV/manual data |
| Telegram Adapter | `src/adapters/telegram/` | Bot webhook → orchestrator → reply |
| Entities (ORM) | `src/entities/` | SQLModel star schema (fact + 6 dims) |

---

## Data Flow

```
User Question (HTTP or Telegram)
        │
        ▼
  NLQRequest (request_id, question)
        │
        ▼
  ┌─────────────────────────────────────┐
  │         Orchestrator                │
  │                                     │
  │  PromptBuilder                      │
  │    ↓ PromptBundle                   │
  │  LLMGateway (Gemini/OpenAI)         │
  │    ↓ LLMRawResponse                 │
  │  SyntacticValidator                 │
  │    ↓ QueryPlan                      │
  │  SemanticValidator                  │
  │    ↓ QueryPlan (validated)          │
  │  SQLCompiler                        │
  │    ↓ CompiledSQL                    │
  │  SQLExecutor                        │
  │    ↓ ResultSet                      │
  │  ResponseBuilder                    │
  │    ↓ QuestionResponse               │
  └─────────────────────────────────────┘
        │
        ▼
  HTTP JSON Response OR Telegram Message
```

**Error flow:** Any stage returning `ErrorResponse` short-circuits the pipeline. No downstream stage executes.

---

## Database Schema (Star Schema)

**Fact Table:** `fact_flight_info`
- PK: `f_flight_combination`
- FKs: departure/destination airport, airline, aircraft, currency
- Attributes: departure/arrival dates, cabin class, trip type, fare, duration, seats remaining

**Dimension Tables:**

| Table | Key Columns |
|-------|-------------|
| `dim_airport` | airport_code, name, city_code |
| `dim_city` | city_code, name, country_code |
| `dim_country` | country_code, name |
| `dim_airline` | airline_code, name |
| `dim_aircraft` | aircraft_code, model |
| `dim_currency_rate` | currency_code, rate |
| `accounts` | user credentials (JWT) |
| `airline_coverage` | coverage rules |

---

## Supported Query Intents (6 total)

Defined in `src/ontology/semantic_layer_v2.json`:

| Intent | Description | Required Params | Optional Params |
|--------|-------------|-----------------|-----------------|
| `cheapest_flight_on_route` | Lowest fare for a route + date range | origin, destination, start_date, end_date | limit |
| `destinations_under_budget` | Reachable destinations under a price cap | origin, max_price, start_date, end_date | limit |
| `destinations_by_country_from_origin` | Destinations in a specific country reachable from origin | origin, country, start_date, end_date | limit |
| `route_fare_options` | All fare options for a route (airline, cabin class, aircraft, duration) | origin, destination, start_date, end_date | limit |
| `airlines_on_route` | Airlines operating a route with cheapest fare + avg duration | origin, destination, start_date, end_date | limit |
| `last_seat_urgency` | Flights with very limited remaining seats (urgency/low-availability alerts) | origin, destination, start_date, end_date | max_seats, limit |

Each intent has: `required_params`, `optional_params`, `sql_template` (parameterized), and examples.

---

## External Integrations

| Integration | Purpose | Auth |
|-------------|---------|------|
| Google Gemini | Primary LLM | `GEMINI_API_KEY` / `LLM_API_KEY` |
| OpenAI | Alternative LLM | `OPENAI_API_KEY` / `LLM_API_KEY` |
| PostgreSQL | Production database | `vault/postgres.user`, `vault/postgres.password` |
| SQLite | Local/dev database | File-based (`DB_PATH`) |
| Telegram Bot API | Webhook messaging | `TELEGRAM_BOT_TOKEN` |
| AWS Lambda | Deployment runtime | IAM role |
| AWS SAM | Infrastructure as Code | AWS credentials |
| OWASP ZAP | Dynamic security scan | CI/CD |
| SonarQube | Code quality | `SONAR_HOST_URL` + token |
| Snyk | Dependency vuln scan | `SNYK_TOKEN` |

---

## Configuration

**`resources/config.toml`** (runtime config):

```toml
[logger]           # Logging handlers and formatters
[service]          # FastAPI host, port, CORS, docs URL
[llm]
  provider = "gemini"
  [llm.providers.gemini]
    model = "gemini-2.5-flash"
    timeout_seconds = 30
  [llm.providers.openai]
    model = "gpt-5.4-nano"
[jwt]              # Expiry (15 min default), algorithm
[datasource]
  [datasource.driver]
    package = "drivers.postgres_driver"
    class = "PostgresDriver"
  [datasource.database]
    drivername = "postgresql+psycopg2"
    host = "localhost"
    port = 5432
    options.user = "postgres.user"       # → vault/postgres.user
    options.password = "postgres.password" # → vault/postgres.password
```

**Environment Variables:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_PROVIDER` | Force provider (`gemini`/`openai`) | Inferred from API key present |
| `LLM_API_KEY` | API key for selected provider | — |
| `GEMINI_API_KEY` | Legacy Gemini key | — |
| `OPENAI_API_KEY` | Legacy OpenAI key | — |
| `DB_PATH` | SQLite path (local dev) | `resources/flights.db` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot auth token | — |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook verification secret | Optional |
| `PROJECT_PATH` | Root dir for config/datasets | `cwd()` |

---

## Testing

**168 tests across 4 layers:**

| Layer | Purpose | Command |
|-------|---------|---------|
| Unit | Fast, mocked component tests | `uv run pytest tests/unit -vv` |
| Integration | Multi-component wiring | `uv run pytest tests/integration -vv` |
| Seam | Orchestrator + 1 real component | Part of integration suite |
| E2E + Golden | Full pipeline with real LLM + DB | `uv run pytest tests/e2e -vv` |

Default run (CI and local): `uv run pytest` — runs all **except** `@pytest.mark.e2e` and `@pytest.mark.external`.

**Golden Questions** (6 regression tests with known expected answers):
- Cheapest flight on route → 6 records, AirAsia Economy at SGD 89
- Destinations under budget → 3 destinations (KUL, BKK, CNX)
- Destinations by country → 2 Thai airports (BKK, CNX)
- Fare options → 6 records across cabin classes
- Airlines on route → 4 airlines
- Last seat urgency → 5 flights with ≤5 seats remaining

---

## CI/CD Pipeline

**GitHub Actions** (`.github/workflows/ontology-ci.yaml`), 3 stages:

1. **Quality & Security** — pytest + coverage, Snyk dependency scan, SonarQube scan
2. **Deploy** (on push to deploy branch / PR to release) — `sam build --use-container` → `sam deploy` → smoke test
3. **ZAP Scan** — OWASP dynamic security scan against deployed Lambda URL

**Deployment target:** AWS Lambda via Lambda Web Adapter pattern (Dockerfile multi-stage build).

---

## Key Design Decisions

### 1. Semantic Model as Source of Truth
Intents, SQL templates, and parameter schemas live in `semantic_layer_v2.json`, not in code. New query types are added by editing JSON — no code changes required.

### 2. Parameterized SQL Only
All SQL uses `:param_name` placeholders bound by the driver. String concatenation/f-strings in SQL are never used.

```python
# Correct
sql = "SELECT * FROM flights WHERE origin = :origin"
params = {"origin": "SIN"}

# Never
sql = f"SELECT * FROM flights WHERE origin = '{origin}'"  # SQL injection risk
```

### 3. Contract-First Development
All pipeline stage inputs/outputs defined via Pydantic models before implementation. Tests written against contracts first.

### 4. Provider Registry Pattern
LLM providers registered in `GatewayRegistry`. Provider selection at startup via:
- `LLM_PROVIDER` env var (explicit override)
- Inferred from which API key is present (if exactly one)
- Default fallback to Gemini

### 5. Vault Pattern for Secrets
Database credentials stored in `vault/` files, referenced by key name in `config.toml`. Prevents hardcoding secrets.

### 6. Dependency Injection via FastAPI Lifespan
All components wired in `startup()` (async context manager) and attached to `app.state`. Routes access via `request.app.state.orchestrator`.

### 7. Error Short-Circuiting
Any pipeline stage can return `ErrorResponse`. The orchestrator detects this and immediately returns the error — no subsequent stages run. All errors include `request_id`, `status`, `error.code`, `error.message`, `error.component`.

### 8. 4-Layer Test Pyramid
- Unit: logic per component (mocked)
- Integration: component wiring (some real)
- Seam: orchestrator + exactly 1 real component
- E2E: full pipeline (real LLM, real DB)

---

## Ingestion Pipeline

**CLI:** `uv run src/batch_main.py --ingestion-type="airport" --project-path="$(pwd)"`

**Flow:**
1. Load `datasets/{type}.yml` (source URL, target table, module/class names)
2. Instantiate `Entry` class (`FileEntry` or `ApiEntry`)
3. Entry delegates to `Ingestion` → `Service` → `DAO` → DB insert/update
4. Secrets resolved from `vault/` files via entity key in config

**Types:**
- **API Ingestion** — airports, cities, airlines, countries, currency rates from upstream REST APIs
- **File Ingestion** — flight facts from CSV (`file:///` URI)
- **Manual Ingestion** — direct row insertion via `POST /ingestion/upload`

---

## Startup / DI Wiring Order (`src/lifecycle_hooks/startup.py`)

1. Load `resources/config.toml`
2. Initialize `DBSession` (create tables if not exist)
3. Register LLM providers (Gemini, OpenAI) in `GatewayRegistry`
4. Resolve active LLM provider (env → infer from API key → default gemini)
5. Load semantic model JSON (cached)
6. Wire all components into `Orchestrator` instance
7. Attach orchestrator, DB session, auth service to `app.state`
