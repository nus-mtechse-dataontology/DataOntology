"""
SQL Compiler tests

Goal in Sprint 1:
- Deterministically translate ValidatedQueryPlan -> SQL + params.
- Ensure output is parameterized (no unsafe string concatenation).
- Reject unsupported constructs explicitly.

Start with these tests:
1) Minimal plan -> expected SQL string structure
2) Filters -> use parameters (e.g., WHERE destination = %s, params=["Tokyo"])
3) group_by -> adds GROUP BY clause
4) Unsupported construct -> clear failure (exception or error object)
"""
import pytest


def test_placeholder_sql_compiler():
    # TODO Sprint 1: implement compile_sql(plan) tests
    assert True
