# Testing Guide

## Purpose
This project uses layered tests so we can move fast without losing confidence:
- Unit tests: fast contract and logic checks per component.
- Integration tests: real wiring across multiple components.
- Seam integration tests: orchestrator + one real component at a time.
- E2E tests: production-like flows with external dependencies (for example, real LLM).

## Test Layers
### Unit (`tests/unit/`)
Use for:
- model contracts
- orchestrator branching logic
- builder formatting behavior

Run:
```bash
uv run pytest tests/unit -vv
```

### Integration (`tests/integration/`)
Use for:
- component wiring and data propagation
- failure short-circuiting across boundaries
- request/response mapping at API level

Run:
```bash
uv run pytest tests/integration -vv
```

### Seam Integration (`tests/integration/orchestrator/`)
Use for:
- orchestrator + one real component, others mocked/faked
- quick fault isolation by boundary

Current seam scaffold files:
- `test_orchestrator_seam_prompt_builder.py`
- `test_orchestrator_seam_syntactic_validator.py`
- `test_orchestrator_seam_semantic_sql_compiler.py`
- `test_orchestrator_seam_sql_executor.py`

Run:
```bash
uv run pytest tests/integration/orchestrator -vv
```

### E2E (`tests/e2e/`)
Use for:
- near-production behavior with external systems
- final confidence before release

Run all E2E:
```bash
uv run pytest tests/e2e -vv
```

Run only tests marked as E2E or external:
```bash
uv run pytest -m "e2e or external" -vv
```

## When To Run What
### During feature development
- Run targeted unit tests for touched modules.
- Run relevant seam/integration tests for changed boundaries.

### Before opening PR
- Run full unit suite.
- Run relevant integration suite(s).

Suggested:
```bash
uv run pytest tests/unit tests/integration -q
```

### Before merging/release
- Run full test suite including E2E (if environment and credentials are available).

```bash
uv run pytest -vv
```

## Useful Commands
Run one test:
```bash
uv run pytest "tests/unit/orchestrator/test_orchestrator.py::test_handle_question_happy_path_returns_success_response_contract" -vv
```

Collect test names without running:
```bash
uv run pytest --collect-only -q
```

Run by keyword:
```bash
uv run pytest -k "orchestrator and failure" -vv
```

