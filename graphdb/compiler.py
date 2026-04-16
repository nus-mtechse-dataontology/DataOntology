"""
Compile SPARQL and SQL templates from semantic_layer_v3.json.

SPARQL: replaces :param_name placeholders with quoted string literals inline
        (dev only — prod uses parameterized binding at the driver level for SQL).
SQL:    returns (template_str, bound_params_dict) — executed via sqlite3 named
        placeholders (:param_name), which is safe at the driver level.
"""
from __future__ import annotations

import re
from config import DEFAULT_LIMIT


# ---------------------------------------------------------------------------
# SPARQL compiler
# ---------------------------------------------------------------------------

def compile_sparql(template: str, params: dict) -> str:
    """
    Substitute :param_name tokens in a SPARQL template with literal values.
    Strings → "value", integers/floats → bare number, booleans → true/false.
    Unknown params are left as-is (SPARQL will reject them, surfacing the bug).
    """
    def _literal(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return f'"{value}"'

    def _replacer(match):
        name = match.group(1)
        if name in params:
            return _literal(params[name])
        return match.group(0)  # leave unreplaced

    return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", _replacer, template)


# ---------------------------------------------------------------------------
# SQL compiler
# ---------------------------------------------------------------------------

def compile_sql(intent_def: dict, params: dict) -> tuple[str, dict]:
    """
    Returns (sql_string, bound_params) for sqlite3 execute().

    Handles:
    - :limit default injection
    - Optional clause appending (trip_type, currency_code) per intent notes
    - destinations_by_duration HAVING dynamic build
    - IN (:destination_airport_codes) expansion for hybrid intents
    """
    template: str = intent_def.get("sql_template", "")
    if not template:
        raise ValueError("Intent has no sql_template")

    bound = {}

    # Collect all params that appear as :name in the template
    placeholders = set(re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", template))

    for ph in placeholders:
        if ph in params:
            bound[ph] = params[ph]

    # Default limit
    if "limit" in placeholders and "limit" not in bound:
        bound["limit"] = DEFAULT_LIMIT

    # --- Optional clause appending (mirrors intent notes) ---
    note = intent_def.get("note", "")

    if "trip_type" in params and "trip_type" not in placeholders:
        if "trip_type" in note:
            template += " AND f.f_trip_type = :trip_type"
            bound["trip_type"] = params["trip_type"]

    if "currency_code" in params and "currency_code" not in placeholders:
        if "currency_code" in note:
            template += " AND f.f_currency_code = :currency_code"
            bound["currency_code"] = params["currency_code"]

    if "cabin_class" in params and "cabin_class" not in placeholders:
        if "cabin_class" in note:
            template += " AND f.f_cabin_class = :cabin_class"
            bound["cabin_class"] = params["cabin_class"]

    # --- destinations_by_duration: dynamic HAVING ---
    if "HAVING" in template and "destinations_by_duration" in intent_def.get("description", ""):
        # Strip the hardcoded HAVING and rebuild
        template = re.sub(r"HAVING\s+.*?(?=ORDER|LIMIT|$)", "", template, flags=re.IGNORECASE).strip()
        having_clauses = []
        if "max_duration_mins" in params:
            having_clauses.append("MIN(f.f_flight_duration) <= :max_duration_mins")
            bound["max_duration_mins"] = params["max_duration_mins"]
        if "min_duration_mins" in params:
            having_clauses.append("MIN(f.f_flight_duration) >= :min_duration_mins")
            bound["min_duration_mins"] = params["min_duration_mins"]
        if having_clauses:
            template += " HAVING " + " AND ".join(having_clauses)

    # --- IN clause expansion for hybrid intents ---
    # destination_airport_codes arrives as a list from SPARQL result
    if "destination_airport_codes" in params:
        codes = params["destination_airport_codes"]
        if isinstance(codes, list):
            placeholders_in = ", ".join(f":code_{i}" for i in range(len(codes)))
            template = template.replace(":destination_airport_codes", placeholders_in)
            for i, c in enumerate(codes):
                bound[f"code_{i}"] = c
        else:
            bound["destination_airport_codes"] = codes

    return template, bound
