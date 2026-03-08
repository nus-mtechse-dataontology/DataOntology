# DataOntology

A Natural Language Query (NLQ) to SQL pipeline — ask questions in plain English, get answers from a flight database.

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

**POST** `/query/query` — Submit a natural language question:

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

All tests should pass on a clean checkout (168 tests).

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
│   ├── response_builder.py          # Formats results for users
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
User Question → PromptBuilder → LLM Gateway (Gemini)
  → SyntacticValidator → SemanticValidator
  → SQLCompiler → SQLExecutor → ResponseBuilder → Answer
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
