Developer Onboarding (DataLens Backend)

This repository contains the backend for DataLens. Sprint 0 (setup, structure, contracts, and test scaffolding) is complete. Sprint 1 focuses on feature implementation only.

Prerequisites
	•	Python 3.11 or newer
	•	Git
	•	uv (Python environment and package manager)

Install uv if not already available:
python3.11 -m pip install –user uv

Clone the repository:
git clone git@github.com:gyhzz/datalens.git
cd datalens/backend

Set up the Python environment:
uv venv
uv pip install -e “.[dev]”

Run the backend:
uv run uvicorn datalens.main:app –reload

The API will be available at:
http://127.0.0.1:8000

Health check endpoint:
GET /health

Run tests:
uv run pytest

All tests should pass on a clean checkout.

Project structure (high level):
	•	api: HTTP API layer
	•	orchestrator: workflow orchestration
	•	planner: NLQ to QueryPlan
	•	grounding: validation and safety checks
	•	compiler: QueryPlan to SQL
	•	executor: SQL execution
	•	ontology: ontology loading and lookup
	•	models: shared data contracts
	•	tests: unit and integration tests

Development workflow:
	•	Contracts are defined in models/
	•	Follow contract-first and test-driven development
	•	Write or update tests before implementing logic
	•	Ensure all tests pass before opening a pull request
