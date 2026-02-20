# Developer Onboarding

This repository contains the app for DataOntology.

### Prerequisites
- Python 3.14 or newer
- Git
- uv (Python environment and package manager)

### Steps
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

4. Run the backend:
```bash
uv run uvicorn app.main:app --reload
```

5. Run tests:
```bash
uv run pytest
```

All tests should pass on a clean checkout.

### Project structure (high level):
- api: HTTP API layer (routers and route modules)
- orchestrator: workflow orchestration
- planner: NLQ to QueryPlan
- grounding: validation and safety checks
- compiler: QueryPlan to SQL
- executor: SQL execution
- ontology: ontology loading and lookup
- models: shared data contracts
- tests: unit and integration tests

### Development workflow:
- Contracts are defined in models/
- Follow contract-first and test-driven development
- Write or update tests before implementing logic
- Ensure all tests pass before opening a pull request

### Documentation:
- See docs/README.md for API notes and local development details.


### Swagger URL:
go to the Swagger API UI: http://127.0.0.1:8000/docs#/

### Redoc URL:
go to the Redoc API UI: http://127.0.0.1:8000/redoc/

### Health check endpoint:
GET http://127.0.0.1:8000/ontology/actuator/health/liveness

GET http://127.0.0.1:8000/ontology/actuator/health/readiness

### To terminate the application:
POST http://127.0.0.1:8000/ontology/actuator/shutdown/

