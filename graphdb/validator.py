"""Validate LLM output against semantic_layer_v3.json — mirrors prod SyntacticValidator + SemanticValidator."""

from __future__ import annotations

import re


def validate(query_plan: dict, semantics: dict) -> tuple[bool, str]:
    """
    Returns (ok, error_message).
    Checks:
      1. Required keys present in query_plan
      2. confidence in range 0.0–1.0
      3. Intent exists in semantic layer
      4. Required params present (unless listed in missing_params)
      5. Param format matches pattern from param_schema
    """
    # 1. Required keys
    for key in ("intent", "parameters", "confidence"):
        if key not in query_plan:
            return False, f"Missing key in LLM output: '{key}'"

    # 2. Confidence range
    confidence = query_plan["confidence"]
    if not (0.0 <= confidence <= 1.0):
        return False, f"Confidence out of range: {confidence}"

    intent_name = query_plan["intent"]
    params = query_plan.get("parameters", {})
    missing = query_plan.get("missing_params", [])

    # 3. Intent exists
    intents = semantics["intents"]
    if intent_name not in intents:
        return False, f"Unknown intent: '{intent_name}'"

    intent_def = intents[intent_name]

    # 4. Required params present (unless LLM flagged them missing)
    for req in intent_def.get("required_params", []):
        if req not in params and req not in missing:
            return False, f"Required param '{req}' missing for intent '{intent_name}'"

    # 5. Param format validation
    schema = semantics.get("param_schema", {})
    for param_name, value in params.items():
        if param_name in schema:
            pattern = schema[param_name].get("pattern")
            if pattern and isinstance(value, str):
                if not re.fullmatch(pattern, value):
                    return False, f"Param '{param_name}' value '{value}' does not match pattern '{pattern}'"

    return True, ""


def print_query_plan(query_plan: dict) -> None:
    intent = query_plan.get("intent", "?")
    params = query_plan.get("parameters", {})
    confidence = query_plan.get("confidence", 0)
    missing = query_plan.get("missing_params", [])
    follow_up = query_plan.get("follow_up_question")

    print(f"\n  Intent     : {intent}")
    print(f"  Confidence : {confidence:.2f}")
    print(f"  Params     : {params}")
    if missing:
        print(f"  Missing    : {missing}")
    if follow_up:
        print(f"  Follow-up  : {follow_up}")
