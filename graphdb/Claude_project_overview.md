# DataOntology — Claude Context Document
_Last updated: 2026-04-16. Reflects verified filesystem state._

---

## What This Project Is

**NLQ → SQL + GraphDB pipeline** for flight/travel data. Users ask plain-English questions and get structured answers. Built as an NUS Software Engineering Master's project.

Two complementary data stores coexist — they are completely independent and communicate only through the Python application layer:

| Layer | Store | Owns | Used for |
|---|---|---|---|
| **SQL** | `fact_flight_info` (SQLite dev / PostgreSQL prod) | Flight transaction data — airport codes, airline codes, aircraft codes, fares, dates, duration, cabin class, trip type, currency | All primary business questions — filtering, aggregation, availability, budgets |
| **GraphDB** | `data_ontology_dml.ttl` (OWL/RDF) | All entity resolution and enrichment — airport names, city/country/continent/region, airline names, aircraft models, safety, weather, attractions, festivals, visa, travel style, etc. | Resolving codes → names; destination enrichment; geographic/semantic filters; route coverage |

**Critical design rule:** `fact_flight_info` contains ONLY codes and numerics (see schema below). There are NO SQL dimension tables. GraphDB is the single source of truth for all entity names and attributes.

---

## Dual-Layer Query Strategy

### Execution Patterns (from `semantic_layer_v3.json`)

**`sql_first` (primary)** — 18 intents
SQL queries `fact_flight_info` using codes only → returns codes + numerics → GraphDB enrichment resolves names and destination context.

**`sparql_then_sql` (hybrid)** — 7 intents
SPARQL asks GraphDB "which airport codes match this filter?" (travel style, safety tier, weather, etc.) → Python holds the code list → SQL uses `IN :destination_airport_codes` to get real fares for those airports.

**`sparql_first` / `sparql_only` (graphdb_primary)** — 7 intents
GraphDB answers the whole question (continent/region lookup, route coverage, visa policy lists, currencies). SQL is an optional bolt-on to validate real flight availability.

**`sparql_first` + `requires_business_result: true` (enrichment)** — 15 intents
After a primary SQL result exists, fires SPARQL per destination airport code to attach city/country context, weather, attractions, safety, transport, festivals, visa, etc.

### How the Two Stores Communicate

They do NOT directly communicate. The **Python application** is the only bridge:

```
SQL result: f_destination_airport_code = "BKK"
           ↓
Python extracts "BKK"
           ↓
SPARQL: ?airport ex:prop_airportCode "BKK" → ?city ?country ?safetyTier ...
           ↓
Python merges both into final response
```

The shared join keys are:
- **Airport code** (`f_destination_airport_code` in SQL ↔ `ex:prop_airportCode` in GraphDB)
- **Airline code** (`f_airline_code` in SQL ↔ `ex:prop_airlineCode` in GraphDB)
- **Aircraft code** (`f_aircraft_code` in SQL ↔ `ex:prop_aircraftCode` in GraphDB)
- **Country code** (`f_destination_country_code` resolved via GraphDB ↔ `ex:prop_countryCode`)

---

## Repo Layout

```
/Users/keewenjie/Desktop/NUS/DataOntology/
├── DataOntology/           ← main Python service (has its own .git)
│   ├── src/                ← application source
│   └── resources/
│       └── semantics/
│           └── semantic_layer_v3.json   ← dual-layer intent/template model
├── graphdb/                ← graph layer scripts + TTL exports
│   ├── build_graphdb_ttl.py             ← reads tmp/ CSVs → writes TTL files
│   ├── data_ontology_ddl.ttl            ← OWL schema (classes + properties)
│   └── data_ontology_dml.ttl            ← RDF instance data (~1.8 MB)
├── tmp/                    ← curated CSV source data + this file
│   ├── fact_flight_info.csv             ← THE ONLY SQL TABLE (codes + numerics)
│   ├── dim_*.csv                        ← source data for GraphDB TTL builder ONLY
│   └── Claude_project_overview.md       ← this file
├── PROJECT_OVERVIEW.md     ← full human-facing overview (canonical reference)
└── tmp.zip
```

The actual git repo root is `DataOntology/DataOntology/` (has `.git`).

> **Important:** All `dim_*.csv` files in `tmp/` are INPUT to `graphdb/build_graphdb_ttl.py`. They are **not** SQL tables and are **not** loaded into any relational database. The only relational data store is `fact_flight_info`.

---

## Application Architecture (7-Stage Pipeline)

```
NLQRequest
  [1] PromptBuilder       → PromptBundle (Jinja2 + semantic_layer_v3.json intents + params)
  [2] LLMGateway          → LLMRawResponse (Gemini or OpenAI)
  [3] SyntacticValidator  → QueryPlan (JSON parse + schema check)
  [4] SemanticValidator   → QueryPlan (intent + param check against v3)
  [5] SQLCompiler         → CompiledSQL (parameterized SQL, fact_flight_info only)
  [6] SQLExecutor         → ResultSet (codes + numerics)
  [7] ResponseBuilder     → QuestionResponse
```

### GraphDB Enhancement (being added — not yet wired)

```
NLQRequest
  [1-4]  same as above
  [5a]  SPARQLCompiler     → CompiledSPARQL (for hybrid/graphdb_primary intents)
  [5b]  SPARQLExecutor     → airport/country code list (for hybrid) OR full result (for graphdb_primary)
  [5c]  SQLCompiler        → CompiledSQL with IN :destination_airport_codes injected
  [6]   SQLExecutor        → ResultSet (codes + numerics from fact_flight_info)
  [6b]  EnrichmentLoop     → fires enrichment SPARQL per destination code from SQL result
  [7]   ResponseBuilder    → merges SQL codes + GraphDB names/context → QuestionResponse
```

**New handlers needed:**
- `SPARQLCompilerHandler` — substitutes `:param_name` in SPARQL templates
- `SPARQLExecutorHandler` — POSTs to GraphDB HTTP endpoint, returns `list[dict]`
- `EnrichmentHandler` — loops over SQL result rows, fires enrichment intents per destination code

**GraphDB HTTP endpoint:** `POST http://localhost:7200/repositories/dataontology`
- Body: `application/x-www-form-urlencoded` with `query=<SPARQL string>`
- Accept: `application/sparql-results+json`
- No third-party client needed — `urllib.request` (already used in codebase) is sufficient

**Entry points:**
- HTTP: `src/main.py` (FastAPI, `DataOntology` class, lifespan = `startup`)
- CLI ingestion: `src/batch_main.py` (Typer)

**DI wiring:** `src/lifecycle_hooks/startup.py` — loads config, wires all components into `Orchestrator`, attaches to `app.state`.

---

## Key Files (verified paths)

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app entry, router wiring |
| `src/lifecycle_hooks/startup.py` | DI wiring + pipeline assembly |
| `src/orchestrator/orchestrator.py` | 7-stage pipeline runner (chain of responsibility) |
| `src/compiler/sql_compiler.py` | QueryPlan → parameterized SQL (fact_flight_info only) |
| `resources/semantics/semantic_layer_v3.json` | **Source of truth** — intents, SQL+SPARQL templates, param schemas |
| `src/prompt_builder/templates/query_plan_prompt.j2` | Jinja2 LLM prompt |
| `src/llm_gateway/providers/gemini_gateway.py` | Gemini provider |
| `src/llm_gateway/providers/openai_gateway.py` | OpenAI provider |

> **Note:** `src/ontology/semantic_layer.json` is the older v2 SQL-only model still used by the live pipeline. `resources/semantics/semantic_layer_v3.json` is v3 (SQL + SPARQL). When v3 is wired in, v2 is retired.

---

## SQL Schema

### SQL Tables

Two tables exist in the relational database:

1. **`fact_flight_info`** — flight transaction data (codes + numerics only, no names)
2. **`dim_accounts`** — user auth + identity data (security-sensitive fields kept in SQL)

### dim_accounts

| Column | Type | Notes |
|--------|------|-------|
| `f_username` | string (PK) | Shared key with GraphDB Account node |
| `f_full_name` | string | Display name — PII, SQL only |
| `f_email` | string | PII, SQL only |
| `f_hashed_password` | string | Argon2id — never leaves SQL |
| `f_disabled` | boolean | Auth status — SQL only |
| `f_passport_country_code` | string (ISO alpha-2) | Denormalised copy for fast JWT/session building at login |

> **Data split rule:** `dim_accounts` in SQL holds ALL fields for auth. GraphDB `Account` node holds ONLY `username` (shared key) + `hasPassportCountry` link to a `Country` node. Full_name, email, hashed_password, disabled are never written to GraphDB.

### fact_flight_info (flight data)

| Column | Type | Description |
|--------|------|-------------|
| `f_flight_combination` | PK | Unique flight record identifier |
| `f_departure_airport_code` | IATA code | Origin airport (3-letter) |
| `f_destination_airport_code` | IATA code | Destination airport (3-letter) |
| `f_airline_code` | IATA code | Operating airline (2-3 chars) |
| `f_aircraft_code` | code | Aircraft type code |
| `f_currency_code` | ISO 4217 | Fare currency |
| `f_departure_date` | datetime | Departure datetime |
| `f_arrival_date` | datetime | Arrival datetime |
| `f_cabin_class` | enum | ECONOMY / BUSINESS / FIRST |
| `f_trip_type` | enum | O = one-way, R = return |
| `f_flight_duration` | integer | Flight duration in minutes |
| `f_total_amount_fare_total` | decimal | Flight fare total (fare only — no hotel/activities) |

**No dimension tables exist in SQL.** SQL queries are simple single-table selects with filters, aggregates, and `IN` clauses. All name resolution (airport name, city, country, airline name, aircraft model) comes from GraphDB.

---

## Graph Layer

### Scripts (`graphdb/`)

| File | Purpose |
|------|---------|
| `build_graphdb_ttl.py` | Reads `tmp/dim_*.csv` source files → writes DDL + DML TTLs |
| `data_ontology_ddl.ttl` | OWL schema (18 classes + 49+ properties) |
| `data_ontology_dml.ttl` | RDF instance data (~1.8 MB) |

**Regenerate TTLs:** `python graphdb/build_graphdb_ttl.py` (run from repo root).

> **Legacy files (not needed):** `build_dim_graph_ttl.py`, `export_city_theme_dims.py`, `export_country_visa_policy_dims.py`, `city_enrichment.py` — all belong to an old pipeline. `build_graphdb_ttl.py` fully supersedes them.

### Current Instance Counts (from DML)

| Entity | Count |
|--------|-------|
| Airports | 909 |
| Airlines | 5 |
| Aircraft | 6 |
| Airline coverage routes | 376 |
| Cities | 870 |
| Countries | 170 |
| City attractions | 462 |
| City cuisines | 166 |
| City festivals | 166 |
| City languages | 136 |
| City monthly weather observations | 1,632 |
| City safety records | 166 |
| City timezones | 166 |
| City travel styles | 488 |
| Subcity areas | 550 |
| Transport modes | 258 |
| Visa requirements | 1,681 |
| Visa policies | 7 |
| Currencies | 170 |
| Currency rates | 129 |
| Accounts | 4 |

### OWL Classes (18)
`Account`, `Aircraft`, `Airline`, `Airport`, `Attraction`, `City`, `CityMonthlyWeather`, `Country`, `CountryVisaRequirement`, `Cuisine`, `Currency`, `Festival`, `Language`, `Route`, `SubcityArea`, `TransportMode`, `TravelStyle`, `VisaPolicy`

### Key Object Properties (19)
`City→Country`, `Airport→City`, `Route→Airline`, `Route→OriginAirport`, `Route→DestinationAirport`, `City→TravelStyle`, `City→CityMonthlyWeather`, `City→SubcityArea`, `City→TransportMode`, `City→Language`, `CountryVisaRequirement→PassportCountry`, `CountryVisaRequirement→DestinationCountry`, `CountryVisaRequirement→VisaPolicy`, `Account→PassportCountry`, `Country→Currency`, `Country→CapitalCity`, `City→Festival`, `City→Cuisine`, `City→Attraction`

### Key Shared Join Keys (SQL ↔ GraphDB)

| Concept | SQL column | GraphDB property |
|---------|-----------|-----------------|
| Airport | `f_departure/destination_airport_code` | `ex:prop_airportCode` |
| Airline | `f_airline_code` | `ex:prop_airlineCode` |
| Aircraft | `f_aircraft_code` | `ex:prop_aircraftCode` |
| Country | resolved via GraphDB airport→city→country chain | `ex:prop_countryCode` |

---

## Curated Dimension Source Files (`tmp/`)

These files are **input to `build_graphdb_ttl.py` only**. They are NOT SQL tables.

### Core vs Descriptive Split

There are two categories of dim files. **Core** tables define the structural skeleton — entities and relationships the query pipeline needs to function. **Descriptive** tables layer enrichment data on top for traveller-facing context.

**Core (9 files — structural, needed for queries to work):**

| File | Purpose |
|------|---------|
| `fact_flight_info.csv` | **SQL only** — flight transactions (codes + numerics) |
| `dim_aircraft.csv` | Aircraft type reference nodes |
| `dim_airline.csv` | Airline reference nodes |
| `dim_airline_coverage.csv` | Route graph edges (airline → origin/destination airports) |
| `dim_airport.csv` | Airport nodes (code, name, city link) |
| `dim_airport_attribute.csv` | Airport amenity properties (terminal count, lounge, transit hotel) |
| `dim_city.csv` | City nodes (code, name, country link) |
| `dim_country.csv` | Country nodes (code, name only — see gap note below) |
| `dim_accounts.csv` | Account nodes — username + passport country link to GraphDB only; all auth fields stay in SQL |

**Descriptive (14 files — enrichment, traveller-facing context):**

| File | GraphDB entities built |
|------|------------------------|
| `dim_city_attraction.csv` | Attraction nodes linked to City |
| `dim_city_country_enrichment.csv` | Continent, region, capital city code, safety index, cost of living index — stored at City level in GraphDB |
| `dim_city_cuisine.csv` | Cuisine nodes linked to City |
| `dim_city_festival.csv` | Festival nodes linked to City |
| `dim_city_language.csv` | Language nodes linked to City |
| `dim_city_monthly_weather.csv` | CityMonthlyWeather nodes (avg temp, rainfall, season, best-time flag) |
| `dim_city_safety.csv` | Safety tier + solo female safe properties on City |
| `dim_city_timezone.csv` | Timezone name + UTC offset on City |
| `dim_city_travel_style.csv` | TravelStyle nodes linked to City |
| `dim_subcity_area.csv` | SubcityArea (neighbourhood) nodes linked to City |
| `dim_transport_mode.csv` | TransportMode nodes linked to City |
| `dim_country_visa_policy.csv` | CountryVisaRequirement nodes |
| `dim_currency.csv` | Currency nodes linked to Country |
| `dim_currency_rate.csv` | Exchange rate properties on Currency |
| `dim_visa_policy.csv` | VisaPolicy reference nodes |

### Country-Level Descriptive Data Gap

`dim_country.csv` currently holds only `f_country_code` and `f_country_name`. There is no file for country-level descriptive/travel context. The following fields are missing and should be added as a new file **`dim_country_description.csv`** when the data is available:

| Field | Type | Description |
|-------|------|-------------|
| `f_country_code` | ISO alpha-2 (PK) | Join key to `dim_country.csv` |
| `f_country_summary` | string | General travel description of the country as a destination |
| `f_official_language` | string | National/official language (cities may have additional local languages) |
| `f_driving_side` | enum: `left` / `right` | Country-wide driving convention |
| `f_electrical_plug_type` | string | Plug standard (A, B, C, G, etc.) |
| `f_electrical_voltage` | string | `110V` / `220V` / `230V` |
| `f_tipping_culture` | enum: `expected` / `optional` / `not_expected` / `offensive` | Cultural tipping norm |
| `f_internet_quality` | enum: `excellent` / `good` / `moderate` / `limited` | Overall country connectivity |
| `f_best_season_to_visit` | string | Country-level generalisation, e.g. "November to March" |
| `f_emergency_number` | string | Police/ambulance number (varies by country) |

> These fields belong at **country level**, not city level, because they are national standards that apply uniformly regardless of which city the traveller is in. When `dim_country_description.csv` is created, `build_graphdb_ttl.py` must be updated to write these as datatype properties on the `Country` node, and a new `country_overview` enrichment intent should be added to `semantic_layer_v3.json`.

---

## Semantic Layer v3 — Intent Summary

Defined in `resources/semantics/semantic_layer_v3.json`.

| Category | Count | Execution pattern |
|---|---|---|
| `primary` | 18 | SQL only (fact_flight_info, no JOINs) |
| `hybrid` | 7 | SPARQL → airport/country code list → SQL IN clause |
| `graphdb_primary` | 9 | SPARQL only (or + optional SQL). Includes `user_passport_country` and `destination_vacation_plan` |
| `enrichment` | 15 | SPARQL per destination code, after SQL result exists |
| **Total** | **49** | |

> `user_passport_country` (graphdb_primary) resolves the logged-in user's passport country from their GraphDB Account node via username from JWT session — allows visa intents to work without the user explicitly stating their passport country.

### `destination_vacation_plan` — Tour Guide Intent

**Added in semantic_layer_v3.json.** A meta-intent that fires when a user wants a full destination guide. Issues **one SPARQL CONSTRUCT query** that traverses the full destination subgraph in a single GraphDB round-trip (airport → city → country → all relationships), then a conditional visa SELECT if `passport_country_code` is available. Formats the combined rdflib graph as a markdown narrative in tour-guide voice.

**Why CONSTRUCT over 13 parallel enrichment queries:** GraphDB's purpose is to traverse relationships in one shot. Individual per-relationship lookups defeat the point — that's what a relational DB is for. One CONSTRUCT captures everything; rdflib walks the graph; ResponseBuilder assembles the narrative. Zero row explosion, zero round-trip fan-out.

**Triggered by prompts like:**
- "Tell me everything about Bangkok for my trip."
- "Give me a vacation guide to Singapore."
- "I'm planning a trip to Tokyo — what should I know?"
- "Plan my vacation to Bali."

**CONSTRUCT query covers (all in one graph traversal):**

| # | Data | GraphDB path | Section in output |
|---|------|-------------|-------------------|
| 1 | City, country, continent, safety, cost of living | Airport → City → Country | Overview |
| 2 | Best months to visit | City → CityMonthlyWeather (bestTimeToVisit=true) | When to go |
| 3 | Airport amenities | Airport properties | Getting there |
| 4 | Transport modes, public transport flag | City → TransportMode | Getting around |
| 5 | Neighbourhoods (pending filtered) | City → SubcityArea | Where to stay |
| 6 | Cuisines | City → Cuisine | What to eat |
| 7 | Attractions (tiered: must_see → popular → local_gem) | City → Attraction | What to see |
| 8 | Festivals | City → Festival | Events |
| 9 | Travel style tags | City → TravelStyle | Travel styles |
| 10 | Currency + exchange rate | Country → Currency | Currency |
| 11 | Timezone + UTC offset | City properties | Timezone |
| 12 | Primary language | City → Language | Language |

**Visa — separate conditional SELECT (`visa_check_for_destination`):** fires only when `passport_country_code` is available (from explicit param or resolved via `user_passport_country` + `username`).

**Optional params for personalisation:**
- `month_num` — personalises weather and festival sections to that specific month
- `passport_country_code` — personalises visa section to user's passport
- `username` — resolves passport country silently from session if passport_country_code not provided

**Output format:** `response_format: "vacation_plan"` — response builder renders as markdown narrative (Option A). Sample output:

```
🗺 Bangkok, Thailand — Vacation Guide
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 OVERVIEW
Southeast Asia | Asia | Capital: Bangkok
Safety: Safe | Solo female: Yes | Cost of living index: 45.2

🌤 BEST TIME TO VISIT
November · December · January · February
Avg temp 28°C · Dry season · Low rainfall

🛬 AIRPORT
Suvarnabhumi (BKK) · International · 2 terminals
✓ Lounge  ✓ Transit hotel

🚇 GETTING AROUND
BTS Skytrain · MRT Metro · Taxi · Tuk-tuk
Public transport widely used in Thailand

🏘 NEIGHBOURHOODS
Sukhumvit     — expats, nightlife, shopping
Silom         — business district, rooftop bars
Rattanakosin  — temples, old city, history

🍜 FOOD
Thai · Street food · Chinese-Thai · Seafood

🎯 ATTRACTIONS
Must-see  : Grand Palace · Wat Pho · Chatuchak Market
Popular   : Asiatique · Jim Thompson House
Local gem : Talat Noi · Bang Krachao

🎪 FESTIVALS (April)
Songkran — cultural · April

✈ TRAVEL STYLES
foodie · nightlife · cultural_heritage · temple_trip · shopping

🛂 VISA (Singapore passport)
Not required · Stay up to 30 days

💱 CURRENCY
Thai Baht (THB) · 1 SGD ≈ 26.3 THB

🕐 TIMEZONE
Asia/Bangkok · UTC+7

🗣 LANGUAGE
Thai
```

**Integration note:** One SPARQL CONSTRUCT query (`sparql_type: "construct"`) fires against GraphDB and returns an RDF graph. Python parses it with `rdflib`. ResponseBuilder walks the graph in the fixed narrative order above. The visa SELECT fires separately and conditionally. No parallel fan-out, no row explosion — this is the correct use of a graph database.

---

## Dev Testing Ground (`/dev`)

Before any changes are integrated into the prod repo (`DataOntology/`), they are tested in a local pipeline script at:

```
/Users/keewenjie/Desktop/NUS/DataOntology/dev/
```

This folder is the **integration sandbox** — it mimics the prod pipeline end-to-end but without the FastAPI/DI/handler chain overhead. Test here first, integrate after.

### Folder Layout

```
dev/
├── pipeline.py          ← main interactive pipeline (keyboard → terminal)
├── config.py            ← paths, API keys, dev defaults (DEV_PASSPORT_COUNTRY)
├── llm.py               ← Gemini call with retry logic
├── compiler.py          ← SPARQL + SQL template compiler
├── sparql_exec.py       ← GraphDB HTTP client (SELECT + CONSTRUCT)
├── db.py                ← SQLite loader + executor
├── loader.py            ← semantic layer loader + prompt context builder
├── response.py          ← all formatters (vacation plan, flight table, attractions, etc.)
├── validator.py         ← query plan validation
├── requirements.txt     ← dev dependencies
└── utility/
    ├── run_tests.py     ← automated test runner (reads/writes tmp/test_cases.csv)
    └── reload_graphdb.py← full GraphDB rebuild + reload in one command
```

### Why

- Avoid breaking the prod pipeline during SPARQL handler development
- Test CONSTRUCT query parsing, SQL compilation, and response formatting locally without deploying
- Fast feedback loop: keyboard prompt → terminal output in one Python script run

### Stack Differences

| Concern | Prod | Dev |
|---------|------|-----|
| Database | PostgreSQL | SQLite (loaded from `tmp/fact_flight_info.csv`) |
| HTTP server | FastAPI + Chain of Responsibility | Single Python script, linear flow |
| LLM | Gemini via pydantic-ai | Gemini via `google-generativeai` SDK directly |
| GraphDB | Remote/cluster | Local at `http://localhost:7200/repositories/dataontology` |
| Input | HTTP POST `/nlq` | Keyboard input (`input()`) |
| Auth/JWT | Full auth middleware | Skipped — `DEV_PASSPORT_COUNTRY` in `config.py` simulates logged-in user |
| Graph parsing | rdflib (to be wired) | rdflib directly |

### Dev Config (`config.py`)

| Setting | Value | Purpose |
|---------|-------|---------|
| `GEMINI_MODEL` | `gemini-2.5-flash` | LLM model |
| `DEFAULT_LIMIT` | `10` | Max rows returned by SQL |
| `GRAPHDB_TIMEOUT` | `30` | GraphDB HTTP timeout (seconds) |
| `DEV_PASSPORT_COUNTRY` | `"IN"` | Simulates logged-in user's passport country for visa enrichment. `IN` (India) requires eVisa for Thailand — good for testing visa display. Set to `None` to test the no-passport fallback. |

### Phase Plan

| Phase | What it tests |
|-------|--------------|
| **1 — LLM intent extraction** | Keyboard prompt → Gemini → intent + params JSON (same `query_plan_prompt.j2` template) |
| **2 — Routing** | Branch by `execution_phase` from semantic_layer_v3.json |
| **3 — SPARQL execution** | Fire SPARQL/CONSTRUCT against local GraphDB; parse CONSTRUCT with rdflib |
| **4 — Visa SELECT** | Conditional visa check SELECT when `passport_country_code` available (falls back to `DEV_PASSPORT_COUNTRY`) |
| **5 — SQL execution** | Compile SQL template → execute against SQLite `fact_flight_info` |
| **6 — Response formatting** | Walk rdflib graph in narrative order → print vacation_plan markdown to terminal |

### Test Runner (`utility/run_tests.py`)

Reads `tmp/test_cases.csv`, runs the next pending case, captures full pipeline stdout, and saves it. **Pass/Fail is not determined automatically** — Claude reviews the output and validates from a business perspective.

**CSV columns:**

| Column | Filled by | Purpose |
|--------|-----------|---------|
| Test ID | Author | Unique identifier |
| Category | Author | Grouping (Primary, Hybrid, VacationPlan, Routing, GraphDB, Enrichment, MissingParams) |
| Test Purpose | Author | What the test is checking |
| Prompt Entered | Author | Exact user question fed into pipeline |
| Actual Intent | Runner | Intent the pipeline detected (auto-parsed from stdout) |
| Actual Phase | Runner | Execution path used (auto-parsed from stdout) |
| Actual Output | Runner | Full pipeline stdout (whitespace-normalised) |
| Intent Pass | Claude | Did the right intent fire? |
| Phase Pass | Claude | Did it use the right execution path? |
| Output Pass | Claude | Is the response useful to a real user (business judgment)? |

**Run:**
```bash
cd /Users/keewenjie/Desktop/NUS/DataOntology/dev/utility
python run_tests.py
```

`BATCH` (default 1) controls how many cases run per invocation. Cases where all 3 Pass columns are filled are skipped.

### GraphDB Reload (`utility/reload_graphdb.py`)

Rebuilds and reloads GraphDB in one command:
1. Runs `graphdb/build_graphdb_ttl.py` → regenerates DDL + DML from `tmp/dim_*.csv`
2. Checks GraphDB is reachable at `localhost:7200`
3. Creates `dataontology` repository if missing (3-strategy fallback for GraphDB 9/10/11 compatibility)
4. Clears all existing triples
5. POSTs `data_ontology_ddl.ttl` (schema)
6. POSTs `data_ontology_dml.ttl` (instance data)
7. Verifies triple count (warns if < 10,000; expects ~54k)

**Run:**
```bash
cd /Users/keewenjie/Desktop/NUS/DataOntology/dev/utility
python reload_graphdb.py
```

### Rules

- Dev script reads `semantic_layer_v3.json` directly from `DataOntology/resources/semantics/` — no copy
- Dev SQLite DB is ephemeral (recreated from CSV each run)
- Once a phase passes end-to-end, the equivalent prod handler is implemented and wired in
- Do not re-discuss design decisions already captured here — refer to this section

---

## External Integrations

| Integration | Auth |
|-------------|------|
| Google Gemini (primary LLM) | `GEMINI_API_KEY` / `LLM_API_KEY` |
| OpenAI (alternative LLM) | `OPENAI_API_KEY` / `LLM_API_KEY` |
| PostgreSQL (prod DB) | `vault/postgres.user`, `vault/postgres.password` |
| SQLite (local dev) | `DB_PATH` env var |
| GraphDB (graph DB) | `http://localhost:7200/repositories/dataontology` (local) |
| Telegram Bot | `TELEGRAM_BOT_TOKEN` |
| AWS Lambda + SAM | IAM role, `template.yaml`, `samconfig.toml` |
| OWASP ZAP | CI/CD scan |
| SonarQube | `SONAR_HOST_URL` + token |
| Snyk | `SNYK_TOKEN` |

---

## Testing

**168 tests across 4 layers:**

| Layer | Command |
|-------|---------|
| Unit | `uv run pytest tests/unit -vv` |
| Integration + Seam | `uv run pytest tests/integration -vv` |
| E2E + Golden | `uv run pytest tests/e2e -vv` |
| All (default, skips e2e/external) | `uv run pytest` |

> Golden tests will need updating when v3 pipeline is wired in — SQL result shape changes (codes only, no joined names).

---

## CI/CD

GitHub Actions (`.github/workflows/ontology-ci.yaml`):
1. **Quality & Security** — pytest + coverage, Snyk, SonarQube
2. **Deploy** (deploy branch / PR to release) — `sam build` → `sam deploy` → smoke test
3. **ZAP Scan** — dynamic security scan against deployed Lambda URL

---

## Ingestion CLI

```bash
uv run src/batch_main.py --ingestion-type="airport" --project-path="$(pwd)"
```

Convenience scripts in `bin/` (e.g. `bin/airport.sh`, `bin/city.sh`).

Modes: **API** (airports, cities, airlines, countries, currency rates), **File** (CSV via `file:///`), **Manual** (`POST /ingestion/upload`).

---

## Config

`resources/config.toml` — LLM provider + model, DB driver, JWT expiry, CORS, service host/port.

Key env vars: `LLM_PROVIDER`, `LLM_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `DB_PATH`, `GRAPHDB_URL`, `TELEGRAM_BOT_TOKEN`, `PROJECT_PATH`.

Secrets: `vault/postgres.user`, `vault/postgres.password`, `vault/destination.apiKey`, `vault/search.apiKey`.
