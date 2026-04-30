# Dev Setup & Instructions
_Last updated: 2026-04-17. Reflects verified filesystem state._

---

## Repo Layout

After cloning, the structure you care about is:

```
DataOntology/               ← git repo root (contains .git)
└── graphdb/                ← dev pipeline lives here
    ├── pipeline.py         ← run this to ask questions
    ├── config.py           ← paste your Gemini key here
    ├── build_graphdb_ttl.py← rebuilds graph data from CSVs
    ├── requirements.txt    ← pip dependencies
    ├── csv_files/          ← all CSV data (dim_*.csv, fact_flight_info.csv, test_cases.csv)
    ├── data_ontology_ddl.ttl
    ├── data_ontology_dml.ttl
    └── utility/
        ├── reload_graphdb.py ← one command to rebuild + load graph
        └── run_tests.py      ← automated test runner
```

All commands below assume you start from the repo root (`DataOntology/`).

---

## Paths to Update for Your Machine

All runtime paths resolve automatically from `Path(__file__).parent` — **no code changes are needed to run the pipeline**. However, three files contain a hardcoded example path in their docstring comments that you may want to update so the `cd` example matches your actual location:

| File | Line | What to change |
|------|------|---------------|
| `graphdb/pipeline.py` | Line 5 | `cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb` → your path |
| `graphdb/utility/run_tests.py` | Line 7 | `cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb/utility` → your path |
| `graphdb/utility/reload_graphdb.py` | Line 5 | `cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb/utility` → your path |

These are comments only — leaving them as-is does not break anything.

The one thing you **must** change before running is the Gemini API key in `graphdb/config.py` (see Step 2 below).

---

## Part 1 — First-Time Setup

### Step 1 — Install Dependencies

```bash
pip install -r graphdb/requirements.txt
```

Installs: `google-genai` (Gemini LLM) and `rdflib` (graph parsing).

### Step 2 — Add Your Gemini API Key

1. Go to https://aistudio.google.com/app/apikey and create a free key
2. Open `graphdb/config.py` and paste it:

```python
GEMINI_API_KEY = "your_key_here"
```

> Free tier = 20 requests/day. If you hit the limit you'll see `[ERROR] Gemini API quota exceeded` — wait until next day or add billing.

### Step 3 — Install and Start GraphDB

GraphDB stores all destination, visa, and enrichment data.

1. Download GraphDB Free: https://www.ontotext.com/products/graphdb/download/
2. Install and launch it
3. Verify it's running — open `http://localhost:7200` in your browser, you should see the GraphDB Workbench

### Step 4 — Load Data into GraphDB

Run this once to build and load all graph data from the CSV files:

```bash
cd graphdb/utility
python reload_graphdb.py
```

Expected output:
```
[1] Rebuilding TTL files from csv_files/dim_*.csv ...
[2] Checking GraphDB at localhost:7200...  Reachable.
[3] Ensuring repository 'dataontology' exists...  Repository created.
[4] Clearing existing triples...  Cleared.
[5] Loading DDL (schema)...  Done — HTTP 204
[6] Loading DML (instance data — may take 30s)...  Done — HTTP 204
[7] Verifying triple count...  54,xxx triples loaded into 'dataontology'
    Ready. Run pipeline.py.
```

---

## Part 2 — Running the Dev Pipeline

```bash
cd graphdb
python pipeline.py
```

Type a question and hit Enter. Type `exit` to quit.

**Things to try:**

| Question | What it tests |
|----------|--------------|
| `What is the cheapest flight from SIN to BKK in June 2026?` | Basic flight search |
| `Where can I fly for a beach holiday from SIN in June 2026?` | Travel style filter (hybrid) |
| `Tell me everything about Bangkok for my trip.` | Full destination guide (CONSTRUCT) |
| `Which countries are visa-free for Singapore passport holders?` | Visa policy list |
| `Do I need a visa to visit Japan with a Singapore passport?` | Specific visa check |
| `Show me flights.` | Vague query → follow-up prompt |

**What you'll see:**
```
[Phase 1] LLM intent extraction
  Intent : cheapest_flight_on_route  Confidence : 1.00
[Phase 2] Routing
  execution_phase : sql_first
[Phase 3] SQL execution
  [sql] 10 row(s)
[Phase 4] Destination enrichment (SPARQL CONSTRUCT)
  [sparql] Graph loaded — 87 triples
[Phase 5] Visa SELECT (conditional)
  [visa] 1 row(s)
[Phase 6] Formatting
============================================================
Flights to Bangkok, Thailand
...
```

### Changing the Simulated Passport

The pipeline simulates a logged-in user. Default passport is `IN` (India), which needs eVisa for Thailand — good for testing visa display. Change it in `graphdb/config.py`:

```python
DEV_PASSPORT_COUNTRY = "IN"   # India — eVisa for Thailand
DEV_PASSPORT_COUNTRY = "SG"   # Singapore — visa-free most places
DEV_PASSPORT_COUNTRY = None   # no passport — shows placeholder
```

---

## Part 3 — Running the Test Runner

The test runner fires pre-defined prompts through the full pipeline, captures stdout, and saves results to `csv_files/test_cases.csv`. Pass/Fail columns are left blank for Claude to review.

```bash
cd graphdb/utility
python run_tests.py
```

Runs 1 case at a time by default. To change, edit `run_tests.py`:
```python
BATCH = 1   # change to 3 to run 3 cases at a time
```

### How the Runner Works

1. Reads `graphdb/csv_files/test_cases.csv`
2. Finds the next row where `Intent Pass`, `Phase Pass`, and `Output Pass` are all blank
3. Runs the prompt through the full pipeline (SQLite + GraphDB)
4. Auto-extracts `Actual Intent` and `Actual Phase` from stdout
5. Saves full pipeline output to `Actual Output`
6. Leaves the 3 Pass columns blank — **Claude fills these on request**

### Getting Validation from Claude

After running tests, open this project in Claude Code and say:
> "validate the results"

Claude reads the CSV and fills in the 3 Pass columns:
- **Intent Pass** — did the pipeline detect the right intent?
- **Phase Pass** — did it use the right execution path?
- **Output Pass** — is the response actually useful to a real user? (business judgment)

### Adding New Test Cases

Edit `graphdb/csv_files/test_cases.csv` and add a new row:

| Column | What to fill |
|--------|-------------|
| Test ID | Next ID, e.g. `TC137` |
| Category | `Primary` / `Hybrid` / `VacationPlan` / `Routing` / `GraphDB` / `Enrichment` / `MissingParams` |
| Test Purpose | One sentence — what this test checks |
| Prompt Entered | The exact question to ask |
| Everything else | Leave blank — runner fills it |

---

## Reference

### Config (`graphdb/config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `GEMINI_API_KEY` | your key | Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | LLM model |
| `DEFAULT_LIMIT` | `10` | Max rows SQL returns |
| `DEV_PASSPORT_COUNTRY` | `"IN"` | Simulated user passport for visa enrichment |
| `GRAPHDB_URL` | `localhost:7200/repositories/dataontology` | GraphDB endpoint |

### Execution Phases

| Phase | Triggered by | What happens |
|-------|-------------|-------------|
| `sql_first` | Flight questions | SQL runs → GraphDB enriches result |
| `sparql_then_sql` | Style/safety filters | GraphDB gets airport codes → SQL filters flights |
| `sparql_only` / `sparql_first` | Visa, destination guides | GraphDB answers the whole question |

### File Locations

| File | Path |
|------|------|
| Pipeline entry point | `graphdb/pipeline.py` |
| Config (API key, passport) | `graphdb/config.py` |
| Semantic layer (intents) | `graphdb/semantic_layer_v3.json` |
| All CSV data | `graphdb/csv_files/` |
| GraphDB schema (DDL) | `graphdb/data_ontology_ddl.ttl` |
| GraphDB instance data (DML) | `graphdb/data_ontology_dml.ttl` |
| GraphDB reload script | `graphdb/utility/reload_graphdb.py` |
| Test runner | `graphdb/utility/run_tests.py` |
| Test cases | `graphdb/csv_files/test_cases.csv` |

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'google'` | Wrong Python. Use `python` (conda), not `/usr/bin/python3` |
| `Cannot reach GraphDB` | Start GraphDB first, then re-run |
| `Gemini API quota exceeded` | 20 req/day free limit. Wait or add billing |
| `FileNotFoundError: fact_flight_info.csv` | Run from `graphdb/` directory, not from inside `utility/` |
| Triple count low after reload | Check GraphDB logs at `http://localhost:7200` |
| `[SQL EXECUTE ERROR] syntax error` | Known bug in some hybrid queries — report to repo owner |

### Known Limitations

| Limitation | Detail |
|-----------|--------|
| Flight data | Only SQ flights in `fact_flight_info.csv` for some routes — data coverage, not a bug |
| No real auth | Passport country is hardcoded in `config.py`, not from a real user session |
| SQLite ≠ PostgreSQL | Dev uses SQLite — some edge cases may differ in prod |
| Test runner history | Always starts fresh — multi-turn context not tested |
