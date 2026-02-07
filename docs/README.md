# Docs

## Local API
- Health check: `GET /health`
- Query: `POST /query` (currently returns 501 until orchestrator is wired)
- Base URL (default): `http://127.0.0.1:8000`

If FastAPI's interactive docs are enabled, you can also visit:
- `GET /docs`
- `GET /redoc`

## Project map
- `app/api/`: HTTP API layer
- `app/orchestrator/`: workflow orchestration
- `app/planner/`: NLQ to QueryPlan
- `app/grounding/`: validation and safety checks
- `app/compiler/`: QueryPlan to SQL
- `app/executor/`: SQL execution
- `app/ontology/`: ontology loading and lookup
- `app/models/`: shared data contracts
- `tests/`: unit and integration tests

## Jira Board
- [Data Ontology Jira Board](https://nus-mtechse-data-ontology.atlassian.net/jira/software/projects/DAT/boards/1)
