# DataOntology — Claude Context Document
_Last updated: 2026-04-25 (session 5). Reflects verified filesystem state._

---

## What This Project Is

**NLQ → SQL + GraphDB pipeline** for flight/travel data. Users ask plain-English questions and get structured answers. Built as an NUS Software Engineering Master's project.

Two complementary data stores coexist — they are completely independent and communicate only through the Python application layer:

| Layer | Store | Owns | Used for |
|---|---|---|---|
| **SQL** | `fact_flight_info` (SQLite dev / PostgreSQL prod) | Flight transaction data — airport codes, airline codes, aircraft codes, fares, dates, duration, cabin class, trip type, currency | All primary business questions — filtering, aggregation, availability, budgets |
| **GraphDB** | `data_ontology_dml.ttl` (OWL/RDF) | All entity resolution and enrichment — airport names, city/country/continent/region, airline names, aircraft models, safety, weather, attractions, festivals, visa, travel style, etc. | Resolving codes → names; destination enrichment; geographic/semantic filters; route coverage |

**Critical design rule:** `fact_flight_info` contains ONLY codes and numerics. There are NO SQL dimension tables. GraphDB is the single source of truth for all entity names and attributes.

---

## How the System Works — End to End

```
User question (plain English)
  │
  ▼
[1] LLM (Gemma 4 / Gemini) reads semantic layer → produces query plan JSON
       {intent, parameters, missing_params, confidence}
  │
  ▼
[2] Validator — checks intent is known, params are valid types/enums
  │
  ▼
[3] Router — reads execution_phase from semantic layer, picks one of 4 paths
  │
  ├──── sql_first ──────────────────────────────────────────────────────────
  │       SQL query on fact_flight_info → rows (codes + numbers)
  │       Optional: SPARQL CONSTRUCT for destination card enrichment
  │
  ├──── sparql_then_sql ────────────────────────────────────────────────────
  │       SPARQL SELECT → list of airport codes matching semantic filter
  │       SQL: WHERE airport_code IN (that list) → rows (codes + numbers)
  │
  ├──── sparql_only / sparql_first ─────────────────────────────────────────
  │       SPARQL SELECT → direct answer (visa lists, route coverage, etc.)
  │
  └──── sparql CONSTRUCT (vacation_plan) ───────────────────────────────────
          One CONSTRUCT query → full destination subgraph (rdflib Graph)
          Optional: conditional visa SELECT
  │
  ▼
[4] Destination name enrichment (all sql paths)
       SPARQL lookup: airport codes → "City, Country (CODE)"
       Applied in-place to SQL result rows before formatting
  │
  ▼
[5] Formatter → human-readable terminal output
```

---

## Dual-Layer Query Strategy

### Execution Patterns (from `semantic_layer_v3.json`)

**`sql_first` (primary)** — 16 intents
SQL queries `fact_flight_info` using codes only → optional GraphDB CONSTRUCT enrichment for destination context.

**`sparql_then_sql` (hybrid)** — 11 intents
SPARQL asks GraphDB "which airport codes match this filter?" (travel style, safety tier, weather, season, attraction type, etc.) → Python holds the code list → SQL uses `IN :destination_airport_codes` to get real fares.

**`sparql_first` / `sparql_only` (graphdb_primary)** — 22 intents
GraphDB answers the whole question (route coverage, visa policy lists, country info, currencies, airport info, festivals, safe destinations, etc.).

**`sparql_first` + `requires_business_result: true` (enrichment)** — 17 intents
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
- **Country code** (resolved via GraphDB airport→city→country chain ↔ `ex:prop_countryCode`)

---

## Repo Layout

```
/Users/keewenjie/Desktop/NUS/DataOntology/
├── DataOntology/           ← main Python service (has its own .git)
│   ├── src/                ← production FastAPI application
│   ├── graphdb/            ← dev pipeline + graph scripts
│   │   ├── pipeline.py          ← interactive dev pipeline (keyboard → terminal)
│   │   ├── config.py            ← paths, API keys, model, dev defaults
│   │   ├── llm.py               ← LLM call with retry + fallback logic
│   │   ├── compiler.py          ← SPARQL + SQL template compiler
│   │   ├── sparql_exec.py       ← GraphDB HTTP client (SELECT + CONSTRUCT)
│   │   ├── db.py                ← SQLite loader + executor
│   │   ├── loader.py            ← semantic layer loader + prompt context builder
│   │   ├── response.py          ← all formatters
│   │   ├── validator.py         ← query plan validation
│   │   ├── data_ontology_dml.ttl ← RDF instance data (~1.8 MB, checked in here for dev)
│   │   ├── Claude_project_overview.md  ← this file
│   │   ├── csv_files/
│   │   │   ├── fact_flight_info.csv     ← flight transactions (codes + numerics)
│   │   │   └── test_cases.csv           ← test cases + results
│   │   └── utility/
│   │       └── run_tests.py     ← automated test runner (reads/writes test_cases.csv)
│   └── resources/
│       └── semantics/
│           └── semantic_layer_v3.json   ← dual-layer intent/template model (source of truth)
├── graphdb/                ← graph layer scripts + TTL exports
│   ├── build_graphdb_ttl.py             ← reads csv_files/ CSVs → writes TTL files
│   ├── data_ontology_ddl.ttl            ← OWL schema (classes + properties)
│   └── data_ontology_dml.ttl            ← RDF instance data (~1.8 MB)
└── tmp/                    ← curated CSV source data (input to build_graphdb_ttl.py only)
```

> **Important:** The `graphdb/csv_files/` directory (inside `DataOntology/`) is what `reload_graphdb.py` reads from. The `tmp/` directory at the repo root is where `build_graphdb_ttl.py` reads its source dim files. These are different locations.

The actual git repo root is `DataOntology/DataOntology/` (has `.git`).

---

## Dev Config (`graphdb/config.py`)

| Setting | Current Value | Purpose |
|---------|--------------|---------|
| `GEMINI_MODEL` | `gemma-4-31b-it` | Primary LLM model |
| `FALLBACK_MODELS` | `["gemini-2.0-flash", "gemini-2.0-flash-lite"]` | Fallback if primary overloaded |
| `MAX_RETRIES` | `40` | Per-model retry limit for transient 500/503 errors |
| `RETRY_DELAY` | `1` | Seconds between retries |
| `DEFAULT_LIMIT` | `10` | Max rows returned by SQL |
| `GRAPHDB_TIMEOUT` | `30` | GraphDB HTTP timeout (seconds) |
| `GRAPHDB_URL` | `http://localhost:7200/repositories/dataontology` | Local GraphDB |
| `DEV_PASSPORT_COUNTRY` | `"IN"` | Simulates logged-in user's passport for visa enrichment. Set to `"SG"` for Singapore-passport queries. Set to `None` to test no-passport fallback. |

**Run dev pipeline:**
```bash
cd /Users/keewenjie/Desktop/NUS/DataOntology/DataOntology/graphdb
python pipeline.py
```

Or via test runner interactive mode:
```bash
cd /Users/keewenjie/Desktop/NUS/DataOntology/DataOntology/graphdb/utility
python run_tests.py
```

---

## SQL Schema

### fact_flight_info (the only SQL table for queries)

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
| `f_total_amount_fare_total` | decimal | Flight fare total (fare only) |

**Coverage:** Primary origins: SIN, KUL, HKG. Dates: Jan–Aug 2026. No September 2026 data.

---

## Semantic Layer v3 — Intent Summary

Defined in `resources/semantics/semantic_layer_v3.json`. **66 intents total** (as of session 5).

| Category | Count | Execution pattern |
|---|---|---|
| `primary` | 16 | SQL only (fact_flight_info, no JOINs) |
| `hybrid` | 11 | SPARQL → airport code list → SQL IN clause |
| `graphdb_primary` | 22 | SPARQL only (standalone) |
| `enrichment` | 17 | SPARQL per destination code, after SQL result exists |
| **Total** | **66** | |

### Full Intent List (grouped by category)

**primary (sql_first):**
`cheapest_flight_on_route`, `cheapest_flight_by_airline`, `route_statistics`, `flights_on_date`, `all_flights_on_date`, `next_available_flight`, `cheapest_month_for_route`, `shortest_flight_on_route`, `shortest_flight_from_origin`, `all_destinations_from_origin`, `destinations_under_budget`, `route_fare_options`, `airlines_on_route`, `aircraft_on_route`, `flight_count_on_route`, `destinations_by_duration`

**hybrid (sparql_then_sql):**
`destinations_by_country_from_origin`, `routes_by_aircraft`, `flights_by_travel_style`, `destinations_by_safety_tier`, `destinations_by_weather_profile`, `destinations_by_attraction_type`, `destinations_by_festival_type`, `destinations_by_transport_mode`, `visa_free_flights_from_origin`, `destinations_by_season` *(new session 5)*, `destinations_good_weather_in_month` *(new session 5)*

**graphdb_primary (sparql_only or sparql_then_sql for geo filters):**
`destinations_by_continent`, `destinations_by_region`, `airlines_covering_route`, `all_routes_from_origin`, `routes_by_airline`, `visa_destinations_by_policy`, `currencies_by_region`, `user_passport_country`, `destination_vacation_plan`, `routes_from_origin_by_country`, `destinations_by_language`, `destinations_with_festivals_in_month`, `cities_in_country` *(new session 4)*, `country_info`, `destinations_by_cost_tier`, `destinations_solo_female_friendly` *(new session 4)*, `currency_exchange_rate` *(new session 4)*, `visa_duration_check` *(new session 4)*, `airports_with_amenity` *(new session 4)*, `safe_destinations_list` *(new session 4)*, `festivals_by_type_global` *(new session 4)*, `airport_info` *(new session 5)*

**enrichment (sparql_first, requires_business_result: true):**
`destination_overview`, `destination_weather_by_month`, `best_months_to_visit`, `destination_attractions`, `destination_festivals`, `destination_travel_styles`, `destination_safety`, `destination_transport`, `destination_cuisines`, `destination_neighborhoods`, `destination_language`, `destination_timezone`, `destination_currency`, `airport_amenities`, `visa_check_for_destination`, `destination_highlights`, `airports_in_city`

### New in Session 5

| Intent | Phase | Key param | Example query |
|--------|-------|-----------|---------------|
| `airport_info` | `sparql_only` | `airport_code` | "Tell me about Changi Airport" / "How many terminals does SIN have?" |
| `destinations_by_season` | `sparql_then_sql` | `season_keyword` + origin + dates | "Summer destinations from SIN in June 2026?" — uses CONTAINS on season_code |
| `destinations_good_weather_in_month` | `sparql_then_sql` | `month_num` + origin + dates | "Where has nice weather in December from SIN?" — filters on `prop_bestTimeToVisit = true` |

### New in Session 4 (recap)

| Intent | Phase | Example query |
|--------|-------|---------------|
| `cities_in_country` | `sparql_only` | "What cities are in Japan?" |
| `destinations_solo_female_friendly` | `sparql_only` | "Safe cities for solo female travel?" |
| `currency_exchange_rate` | `sparql_only` | "What is 1 SGD in JPY?" |
| `visa_duration_check` | `sparql_only` | "How long can I stay in Australia?" |
| `airports_with_amenity` | `sparql_only` | "Which airports have transit hotels?" |
| `safe_destinations_list` | `sparql_only` | "Show me very safe destinations" |
| `festivals_by_type_global` | `sparql_only` | "What music festivals are there?" |

---

## Graph Layer

### Key TTL Properties (important gotchas)

- `prop_capitalCity` stores a **URI** (`ex:City_TYO`), NOT a string. Always dereference: `?country ex:prop_capitalCity ?cap . ?cap ex:prop_cityName ?capitalCityName`
- `prop_soloFemaleSafe` is a boolean triple (`true`/`false`)
- `prop_safetyTier` is a string (`"very_safe"`, `"safe"`, `"moderate"`, `"caution"`)
- `prop_bestTimeToVisit` is a boolean on weather observation nodes
- City codes vs airport IATA codes: `City_SPK` (Sapporo city) ≠ `Airport_CTS` (New Chitose, the actual airport serving Sapporo). Routes attach to airport nodes via `prop_inCity`.
- Airport attribute properties: `prop_terminalCount`, `prop_airportType`, `prop_isInternational`, `prop_hasLounge`, `prop_hasTransitHotel`

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

### season_code Values (used by `destinations_by_season`)
`autumn`, `autumn_peak`, `autumn_shoulder`, `cold_snowy`, `cool_dry`, `cool_shoulder`, `cool_wet`, `cool_winter`, `dry_season`, `hot_season`, `humid_season`, `monsoon`, `northeast_monsoon`, `pleasant_peak`, `post_monsoon`, `pre_monsoon`, `rainy_season`, `shoulder`, `spring`, `spring_peak`, `spring_shoulder`, `summer`, `summer_peak`, `summer_warm`, `typhoon_risk`, `typhoon_summer`, `warm_season`, `wet_cool`, `wet_season`, `wettest_season`, `winter`, `winter_peak`, `winter_wet`

`destinations_by_season` uses `CONTAINS(LCASE(seasonCode), LCASE(:season_keyword))` — "summer" matches summer, summer_peak, summer_warm. "dry" matches dry_season.

---

## Known Data Gaps

| Gap | Status |
|-----|--------|
| NRT/Tokyo — no weather, transport, or language data | Pending data addition |
| LHR/London — no weather, transport, or language data | Pending data addition |
| DPS/Bali — transport mode data incorrect | Pending fix |
| SYD — no Metro transport mode | Pending data addition |
| Missing festivals: Tokyo Hanami, Sydney Australia Day, HKG CNY, Bali Galungan, SYD NYE | Pending data addition |
| Some airports have weather but no season_code classification | Pending data addition |
| KLU flight duration data error in fact_flight_info.csv | Pending fix |
| Australia visa: was `visa_not_required` — **fixed session 5** to `eta_required` (ETA required, not visa-free) | Fixed in TTL |
| `routes_by_aircraft` — LLM aircraft model name format mismatch | Pending semantic layer fix (CONTAINS) |
| Wrong airport code for Tokyo/London queries (LLM resolves to wrong code) | Pending disambiguation examples |

---

## Pipeline Bugs Fixed (all sessions)

### Session 5 (2026-04-25)

**Multi-leg query crash (`pipeline.py`):**
- Trigger: "Germany to Australia back to Singapore" — LLM returned a list of query plans
- Root cause: `query_plan` was a list; `print_query_plan(query_plan)` calls `.get()` which lists don't have
- Fix: Added `isinstance(query_plan, list)` guard at line 124 → returns: "I can only look up one flight at a time. Please ask about each leg separately."

**Australia visa data (`data_ontology_dml.ttl`):**
- Was: `prop_visaRequired false`, `VisaPolicy_visa_not_required`
- Fix: `prop_visaRequired true`, `VisaPolicy_eta_required`, added `prop_onlineApplyUrl`

**`country_info` capital URI (`semantic_layer_v3.json` + `response.py`):**
- Was: SPARQL returned raw URI `http://dataontology.example/graph/City_TYO` for capital field
- Root cause: `prop_capitalCity` stores a URI, not a string literal
- Fix: SPARQL now dereferences: `?country ex:prop_capitalCity ?cap . ?cap ex:prop_cityName ?capitalCityName`
- Formatter updated to read `capitalCityName` instead of `capitalCity`

### Session 4 (2026-04-25)

- SQL optional clause injection: `f_trip_type`, `f_currency_code`, `f_cabin_class` appended after LIMIT → fixed with `_insert_before_group_or_order()` helper in `compiler.py`
- `destinations_by_duration` HAVING clause position → fixed with `_insert_before_order()`
- `routes_by_aircraft` IN clause expansion: only `destination_airport_codes` was expanded → loop now handles `aircraft_codes` (prefix `ac`) too
- `visa_check_for_destination`: no dispatch → fell to `format_table` → `visaDurationDays` shown as "1h30m" → fixed with `format_visa_check()` + dispatch
- `flight_count_on_route`: no formatter → raw column names → fixed with `format_flight_count()`
- `destination_highlights`: raw airport code as heading → fixed: pipeline resolves city name via `_resolve_airport_names()` and injects `params["city_name"]`
- `destination_festivals`: fetched all months but didn't filter → fixed: `format_festivals()` filters by `monthNum`
- `cheapest_month_for_route`: showed `2026-06` → fixed with `_fmt_month()` helper
- Bare `return` → `return query_plan` in 3 early-exit paths (sparql_then_sql empty codes, return-trip path, date-out-of-range)
- 6 new `sparql_only` intents added + `cities_in_country` + `country_info` capital dereference fix

### Session 2–3 (2026-04-18 to 2026-04-23)

- Full `response.py` rewrite: removed ASCII table borders, raw column names, added `_humanize()`, `_fmt_dur()`, `_fmt_dt()`, `_fmt_fare()`, `POLICY_DISPLAY` dict
- `destinations_by_continent` / `destinations_by_region`: `sparql_first` → `sparql_then_sql` (was returning geography without checking real flight availability)
- `destinations_by_weather_profile` SPARQL UNION + `_strip_unresolved_union_branches()` in compiler
- LLM retry hardening: MAX_RETRIES 10→40, RETRY_DELAY 3s→1s, added 500 to retryable set
- Test runner redesign: LLM Output caching column, auto-clear output columns, debug line stripping via `_DEBUG_RE`

---

## Pending Code Backlog

All these are identified but not yet implemented:

### response.py
| # | Issue | Description |
|---|-------|-------------|
| NEW3 | `destinations_by_duration` header | Shows short/medium/long-haul without a clear header |
| NEW4/H1 | Bare-bullet intents | 4 intents output bullets with no header (country, festival-type, transport-mode, visa-free) |
| TG9 | Attraction filter empty | No message when filtered attraction type has 0 results |
| TG10 | Silent reinterpretation | When query is silently reinterpreted, should prepend context line |
| M9/M12 | Empty-state messages | Wording and leading-indent issues |
| TG3 | Departures footer | Add "Showing N of M departures" count |
| TG1 | Raw URL | Wrap apply URL in HTML anchor tag |
| M6 | Cuisine one-word label | Expand to dishes list or remove if too thin |

### pipeline.py
| # | Issue | Description |
|---|-------|-------------|
| C4 | Passport parenthetical | "(India)" appears next to visa line — remove |
| NEW-H | Missing origin | `sparql_then_sql` without origin should route to follow-up |
| NEW-I | Month-level date | Follow-up should accept "in June" not just exact date |
| TG12 | Date format | `destinations_under_budget` follow-up shows wrong date format |

### Semantic layer
| # | Issue | Description |
|---|-------|-------------|
| NEW-J | `routes_by_aircraft` | Use `CONTAINS` for aircraft model name matching |
| NEW-G | City disambiguation | Add Tokyo/London airport disambiguation examples |

### Data
| # | Issue | Description |
|---|-------|-------------|
| — | NRT/LHR transport | Add transport modes for Tokyo, London |
| — | NRT/LHR language | Add Japanese for Tokyo, English for London |
| — | NRT/LHR weather | Add 12-month weather records |
| — | Missing festivals | Tokyo Hanami, Sydney Australia Day, HKG CNY, Bali Galungan, SYD NYE |
| NEW-F | Season codes | Add season_code to airports with weather but no season classification |
| M8 | KLU duration | Fix KLU flight duration in fact_flight_info.csv |

---

## `destination_vacation_plan` — Tour Guide Intent

A meta-intent that fires when a user wants a full destination guide. Issues **one SPARQL CONSTRUCT query** that traverses the full destination subgraph (airport → city → country → all relationships) in a single GraphDB round-trip.

**Triggered by:** "Tell me everything about Bangkok", "Plan my trip to Tokyo", "Give me a vacation guide to Bali"

**CONSTRUCT covers (one query):** city/country/safety/cost, best months, airport amenities, transport modes, neighbourhoods, cuisines, attractions (tiered), festivals, travel styles, currency, timezone, language.

**Visa** — separate conditional SELECT (`visa_check_for_destination`), fires only when `passport_country_code` is available.

---

## Test Suite

```bash
cd /Users/keewenjie/Desktop/NUS/DataOntology/DataOntology/graphdb/utility
python run_tests.py
```

Currently in **interactive demo mode** (batch execution commented out). To re-enable batch, uncomment the batch block in `run_tests.py`.

### LLM Output Caching
`LLM Output` column caches raw Gemini plan JSON. On re-run, the column is preserved → Gemini is skipped, formatter is re-run with cached plan. To force fresh Gemini call, blank a row's `LLM Output` field.

Output columns (`Response`, `Actual Intent`, `Actual Phase`, `Error`, pass columns) are auto-cleared at every run start. `LLM Output` is never cleared.

### Last Full Run (2026-04-24)
245/245 responses, 0 errors, 0 missing LLM Output, 100% Gemini cache hit. Test suite not yet re-run against session 4/5 changes.

---

## Application Architecture (Production)

### Dev Pipeline (`graphdb/pipeline.py`)

```
NLQRequest
  [1] LLMGateway          → QueryPlan JSON (Gemma / Gemini via google-genai SDK)
  [2] SyntacticValidator  → checked: JSON parse + schema; list guard (multi-leg queries)
  [3] SemanticValidator   → checked: intent known + params valid
  [4] Router              → branch by execution_phase (4 patterns)
  [5] SPARQLCompiler      → CompiledSPARQL (for hybrid / graphdb_primary / construct intents)
  [5] SQLCompiler         → CompiledSQL (parameterized, fact_flight_info only)
  [6] Executor            → SQLite rows + GraphDB result (SELECT or CONSTRUCT graph)
  [7] DestinationEnricher → SPARQL lookup: raw airport codes → "City, Country (CODE)"
  [8] ResponseFormatter   → human-readable output
```

### Prod Pipeline (`src/orchestrator/orchestrator.py`)

FastAPI chain-of-responsibility pattern. Same logical stages as dev but wired via DI in `src/lifecycle_hooks/startup.py`. Uses PostgreSQL instead of SQLite.

---

## Curated Dimension Source Files (`graphdb/csv_files/`)

These files are loaded by `reload_graphdb.py` to rebuild the GraphDB TTL.

**Core:** `dim_aircraft.csv`, `dim_airline.csv`, `dim_airline_coverage.csv`, `dim_airport.csv`, `dim_airport_attribute.csv`, `dim_city.csv`, `dim_country.csv`, `dim_accounts.csv`

**Descriptive (enrichment):** `dim_city_attraction.csv`, `dim_city_country_enrichment.csv`, `dim_city_cuisine.csv`, `dim_city_festival.csv`, `dim_city_language.csv`, `dim_city_monthly_weather.csv`, `dim_city_safety.csv`, `dim_city_timezone.csv`, `dim_city_travel_style.csv`, `dim_subcity_area.csv`, `dim_transport_mode.csv`, `dim_country_visa_policy.csv`, `dim_currency.csv`, `dim_currency_rate.csv`, `dim_visa_policy.csv`

**Fact (SQL only):** `fact_flight_info.csv`

> **Note:** The `dim_*.csv` files here are **not** SQL tables. They are source data for `build_graphdb_ttl.py` → TTL → GraphDB only. The only relational fact table is `fact_flight_info`.

---

## External Integrations

| Integration | Auth |
|-------------|------|
| Google Gemini / Gemma (LLM) | `GEMINI_API_KEY` in `config.py` |
| GraphDB (graph DB) | `http://localhost:7200/repositories/dataontology` (local) |
| PostgreSQL (prod DB) | `vault/postgres.user`, `vault/postgres.password` |
| SQLite (local dev) | Loaded from `csv_files/fact_flight_info.csv` at startup |
| Telegram Bot | `TELEGRAM_BOT_TOKEN` |
| AWS Lambda + SAM | IAM role, `template.yaml`, `samconfig.toml` |

---

## Quick Reference — Common Queries by Intent

| Question type | Intent | Phase |
|---------------|--------|-------|
| "Cheapest flight SIN to BKK in June" | `cheapest_flight_on_route` | sql_first |
| "Flights on 30 May from SIN" | `all_flights_on_date` | sql_first |
| "Tell me about Bangkok" | `destination_vacation_plan` | sparql CONSTRUCT |
| "What cities in Japan from SIN?" | `routes_from_origin_by_country` | sparql_only |
| "What cities are in Japan?" | `cities_in_country` | sparql_only |
| "Tell me about Japan (country info)" | `country_info` | sparql_only |
| "Tell me about Changi Airport" | `airport_info` | sparql_only |
| "Do I need a visa to go to Japan?" | `visa_check_for_destination` | sparql_first (enrichment) |
| "How long can I stay in Australia?" | `visa_duration_check` | sparql_only |
| "Visa-free destinations from SIN" | `visa_free_flights_from_origin` | sparql_then_sql |
| "Safe destinations from SIN in June" | `destinations_by_safety_tier` | sparql_then_sql |
| "Summer destinations from SIN in June" | `destinations_by_season` | sparql_then_sql |
| "Nice weather in December from SIN" | `destinations_good_weather_in_month` | sparql_then_sql |
| "What is 1 SGD in JPY?" | `currency_exchange_rate` | sparql_only |
| "Solo female safe destinations?" | `destinations_solo_female_friendly` | sparql_only |
| "Airports with transit hotels?" | `airports_with_amenity` | sparql_only |
| "Music festivals around the world?" | `festivals_by_type_global` | sparql_only |
| "Beach holiday from SIN on 15 Jun" | `flights_by_travel_style` | sparql_then_sql |
