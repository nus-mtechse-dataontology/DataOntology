"""
Planner tests (stub or LLM-backed)

Goal in Sprint 1:
- Planner generates a QueryPlan matching the contract.
- If output is invalid, it should be rejected/raised before grounding.

Start with these tests:
1) Known NLQ -> valid QueryPlan:
   - QueryPlan.model_validate(output) passes
2) Output does not include unexpected fields (if you enforce strictness)
3) Bad NLQ handling:
   - empty/garbage input returns structured failure (or raises a specific exception)
4) (If LLM-backed later)
   - non-JSON output is rejected
   - invalid JSON shape is rejected
"""
import pytest


def test_placeholder_planner():
    # TODO Sprint 1: implement with stub planner mapping NLQs -> QueryPlan
    assert True
