"""
Grounding/Validation tests (hero feature)

Goal in Sprint 1:
- Reject malformed or semantically invalid plans.
- Enforce safety rules (read-only, allowlist fields).
- Return consistent error structure.

Start with these tests:
1) Schema validation:
   - missing required fields -> rejected (error_code like "INVALID_SCHEMA")
2) Semantic grounding:
   - unknown source -> rejected ("UNKNOWN_SOURCE")
   - unknown select field -> rejected ("UNKNOWN_FIELD")
   - unknown filter key -> rejected ("UNKNOWN_FILTER")
3) Security/policy:
   - enforce read-only behavior (if operation exists, must be read)
   - enforce query limits (later): max rows, no wildcards, etc.
4) Success:
   - valid QueryPlan -> returns ValidatedQueryPlan
"""
import pytest


def test_placeholder_grounding():
    # TODO Sprint 1: implement validate(plan, ontology) tests
    assert True

