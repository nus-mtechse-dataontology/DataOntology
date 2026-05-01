# DataOntology

A Natural Language Query (NLQ) to SQL pipeline — ask questions in plain English, get answers from a flight database.

## Run on Local using Docker
### pre-requisites
- aws installation is setup using the script given and configure AWS profile
- Run RDS connect script to start the secure tunnel to connect to RDS

### running the app
- docker build --no-cache -t data-ontology-api .
- docker run -p 9000:8000  -e GEMINI_API_KEY="<REPLACE-WITH-GEMINI-API-KEY>"  -e DB_PASSWORD="<REPLACE-WITH-DB-PASSWORD" data-ontology-api

### Running tests
- curl -X POST http://localhost:9000/query/query -H "Content-Type: application/json" -d '{"request_id":"test-1","question":"What is the cheapest return flight from SIN to BKK from 2026-06-01 to 2026-06-15?","start_date":"2026-06-01","end_date":"2026-06-15","origin":"SIN","destination":"BKK"}'


## Run on local using uv
### Prerequisites
- Python 3.14 or newer
- Git
- uv (Python environment and package manager)

### Setup

1. Install uv if not already available:
```bash
python3.14 -m pip install --user uv
```

2. Clone the repository:
```bash
git clone git@github.com:nus-mtechse-dataontology/DataOntology.git
```

3. Set up the Python environment:
```bash
uv venv
uv pip install -e ".[dev]"
```

4. Create a `.env` file in the repository root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DB_PATH=resources/flights.db
```

### Running the app

```bash
uv run python src/main.py
```

The server starts at http://127.0.0.1:8000

### Querying the API

**POST** `/query/query` — Submit a natural language question (returns a plain text stream):

```bash
curl -X POST http://localhost:8000/query/query \
  -H "Content-Type: application/json" \
  -d '{"request_id": "test-1", "question": "What is the cheapest return flight from SIN to BKK?"}'
```

**GET** `/query/get_query` — Health check:

```bash
curl http://localhost:8000/query/get_query
```

### Running tests

```bash
uv run pytest
```

All tests should pass on a clean checkout (223 tests).

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | API key for Google Gemini LLM |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model name |
| `DB_PATH` | No | `resources/flights.db` | Path to SQLite database |
| `SEMANTIC_MODEL_PATH` | No | `src/ontology/semantic_layer.json` | Path to semantic model |

### Project Structure

```
src/
├── main.py                          # Application entry point
├── lifecycle_hooks/startup.py       # Dependency wiring (Orchestrator setup)
├── endpoints/routes/
│   ├── query/query_routes.py        # POST /query/query endpoint
│   └── telegram/telegram_routes.py  # Telegram webhook endpoint
├── orchestrator/
│   ├── orchestrator.py              # 7-stage NLQ pipeline runner
│   └── handlers/                    # Pipeline handlers (Request, Prompt, LLM, Validators, Compiler, Executor)
│   └── response_formatter_handler.py # Formats results for users
│   └── error_response_builder.py    # Standardised error responses
├── prompt_builder/                  # Builds LLM prompts from templates
├── llm_gateway/providers/           # LLM integrations (Gemini, OpenAI)
├── validators/
│   ├── syntactic/                   # Parses LLM JSON → QueryPlan
│   └── semantic/                    # Validates intent, params, formats
├── compiler/sql_compiler.py         # Compiles QueryPlan → parameterised SQL
├── execution/sql_executor.py        # Executes SQL against SQLite
├── ontology/                        # Semantic model files (JSON)
├── models/                          # Shared Pydantic data contracts
└── configurations/                  # App, admin, logger config

tests/
├── unit/                            # Component-level tests
└── integration/                     # Seam tests and full pipeline tests
```

### Pipeline Flow

```
User Question → RequestHandler → PromptBuilder → LLM Gateway (Gemini)
  → SyntacticValidator → SemanticValidator
  → SQLCompiler → SQLExecutor → ResponseFormatterHandler → Answer
```

### Development Workflow
- Contracts are defined in `models/`
- Follow contract-first and test-driven development
- Write or update tests before implementing logic
- Ensure all tests pass before opening a pull request

### API Docs
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc/
- Health: http://127.0.0.1:8000/ontology/actuator/health/liveness

---

## Local E2E Testing (Telegram Bot)

### One-time setup

1. Create a Telegram bot via [@BotFather](https://t.me/botfather) and save the `TELEGRAM_BOT_TOKEN`
2. Install ngrok and authenticate:
```bash
brew install ngrok
ngrok config add-authtoken <your-ngrok-authtoken>
```
3. Set vault credentials for local Postgres:
```bash
echo -n "postgres" > vault/postgres.user
echo -n "postgres" > vault/postgres.password
```

### Every session

1. Start local Postgres:
```bash
docker run --name dataontology \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=data_ontology \
  -p 5432:5432 -d postgres
```
If the container already exists: `docker start dataontology`

2. Load seed data:
```bash
psql -h localhost -U postgres -d data_ontology -f resources/seed_local.sql
```

3. Start the server:
```bash
export GEMINI_API_KEY=<your-gemini-api-key>
export TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
uv run python src/main.py
```

4. Start ngrok in a separate terminal:
```bash
ngrok http 8000
```
Copy the `https://....ngrok-free.dev` URL from the output.

5. Register the webhook with Telegram (required each session — ngrok URL changes on restart):
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<ngrok-url>/telegram/webhook"}'
```

### Test questions

Send these to your bot in Telegram to verify each intent, or run them automatically (see below):

| Intent | Question |
|---|---|
| Cheapest flight on route | `What is the cheapest flight from SIN to BKK between 1 June and 30 June 2025?` |
| Destinations under budget | `Where can I fly from SIN for under 300 SGD between 1 June and 30 June 2025?` |
| Destinations by country | `From SIN, which airports in Thailand can I fly to in June 2025?` |
| All fare options | `Show me all fare options from SIN to BKK between 1 June and 30 June 2025` |
| Airlines on route | `Which airlines fly from SIN to BKK in June 2025?` |
| Last seat urgency | `Are there any almost-full flights from SIN to BKK in June 2025?` |

### Additional intent examples

These require the broader 2026 flight facts and GraphDB ontology data:

| Intent | Question |
|---|---|
| Destinations by country and date range | `What flights from Singapore to Australia are available from 2 June 2026 to 8 June 2026?` |
| Destinations by country on weekends | `What flights from Singapore to Australia are available on weekends in June 2026?` |

### Expected results

- **Cheapest flight** — 6 records, AirAsia Economy at SGD 89 cheapest
- **Under budget** — 3 destinations (KUL, BKK, CNX), NRT excluded as it exceeds 300 SGD
- **Thailand airports** — 2 airports (BKK, CNX)
- **Fare options** — 6 records across Economy and Business
- **Airlines** — 4 airlines (AirAsia, Malaysia Airlines, Thai Airways, Singapore Airlines)
- **Last seat urgency** — 5 flights with ≤5 seats remaining

### Running golden questions automatically

The same questions are codified as e2e tests and can be run directly against the orchestrator (no Telegram or ngrok needed):

```bash
uv run pytest -m e2e -v
```

Requires local Postgres running with seed data and `GEMINI_API_KEY` set. These tests are excluded from the default `uv run pytest` run and must be triggered deliberately.
