"""
Orchestrator tests

Goal in Sprint 1:
- Orchestrator enforces the workflow order and fail-fast behavior.
- Orchestrator normalizes failures into ErrorResponse.

Start with these tests:
1) Happy path (with stubs/mocks):
   - execute(nlq) calls: load_ontology -> planner -> grounding -> compiler -> executor
2) Fail-fast:
   - if grounding fails, compiler/executor are NOT called
3) Contract enforcement:
   - planner output is validated as QueryPlan
   - grounding output is ValidatedQueryPlan
4) Error normalization:
   - any component exception becomes ErrorResponse with correct stage + code
"""
import pytest


def test_placeholder_orchestrator():
    # TODO Sprint 1: implement using mocks for each component
    assert True
