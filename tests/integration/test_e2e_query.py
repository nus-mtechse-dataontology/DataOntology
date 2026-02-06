"""
End-to-end integration tests

Goal in Sprint 1:
- Prove the full pipeline works together end-to-end, even if planner is stubbed.

Start with these tests:
1) Happy path:
   - NLQ -> QueryPlan -> ValidatedQueryPlan -> SQL -> DB -> results
2) Rejection path:
   - NLQ -> invalid plan -> grounding rejects -> ErrorResponse returned
3) (Later) adversarial input:
   - prompt injection attempt -> blocked at grounding
"""
import pytest


def test_placeholder_e2e():
    # TODO Sprint 1: run against local app + local DB (docker compose)
    assert True
