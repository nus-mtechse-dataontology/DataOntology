"""
Compile SPARQL and SQL templates from semantic_layer_v3.json.

SPARQL: replaces :param_name placeholders with quoted string literals inline
        (dev only — prod uses parameterized binding at the driver level for SQL).
SQL:    returns (template_str, bound_params_dict) — executed via sqlite3 named
        placeholders (:param_name), which is safe at the driver level.
"""
import re
from .config import DEFAULT_LIMIT


# ---------------------------------------------------------------------------
# SPARQL compiler
# ---------------------------------------------------------------------------

def compile_sparql(template: str, params: dict) -> str:
    """
    Substitute :param_name tokens in a SPARQL template with literal values.
    Strings → "value", integers/floats → bare number, booleans → true/false.

    After substitution, any top-level { ... } block in a UNION chain that still
    contains an unresolved :param_name token is removed (along with its UNION
    keyword), so partially-optional UNION templates don't produce 400 errors.
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

    compiled = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", _replacer, template)
    return _strip_unresolved_union_branches(compiled)


# Bare :param_name — NOT preceded by a word char (so ex:prop_foo is excluded).
_UNRESOLVED_PARAM = re.compile(r"(?<!\w):[A-Za-z_][A-Za-z0-9_]*")


def _strip_unresolved_union_branches(sparql: str) -> str:
    """
    In UNION expressions, remove flat (non-nested) branches that still contain
    unresolved :param_name placeholders.

    Pattern handled:  { left_branch } UNION { right_branch }
    If left is bad  → keep only { right_branch }
    If right is bad → keep only { left_branch }
    If both bad     → remove both and the UNION keyword

    Works for flat branches only (no nested braces inside the branch).
    All current templates use this pattern.
    """
    if not re.search(r"\bUNION\b", sparql, re.IGNORECASE):
        return sparql

    def _pick_branch(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        left_bad  = bool(_UNRESOLVED_PARAM.search(left))
        right_bad = bool(_UNRESOLVED_PARAM.search(right))
        if left_bad and right_bad:
            return ""
        if left_bad:
            return "{" + right + "}"
        if right_bad:
            return "{" + left + "}"
        return m.group(0)  # both resolved — keep full UNION

    return re.sub(
        r"\{([^{}]*)\}\s*UNION\s*\{([^{}]*)\}",
        _pick_branch,
        sparql,
        flags=re.IGNORECASE,
    ).strip()


# ---------------------------------------------------------------------------
# SQL compiler
# ---------------------------------------------------------------------------

def _insert_before_group_or_order(template: str, clause: str) -> str:
    """Insert a WHERE-clause fragment before GROUP BY / HAVING / ORDER BY / LIMIT."""
    m = re.search(r"\s+(?:GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT)\b", template, re.IGNORECASE)
    if m:
        return template[:m.start()] + " " + clause + template[m.start():]
    return template + " " + clause


def _insert_before_order(template: str, clause: str) -> str:
    """Insert a clause before ORDER BY / LIMIT (used to place HAVING after GROUP BY)."""
    m = re.search(r"\s+(?:ORDER\s+BY|LIMIT)\b", template, re.IGNORECASE)
    if m:
        return template[:m.start()] + " " + clause + template[m.start():]
    return template + " " + clause


def compile_sql(intent_def: dict, params: dict, intent_name: str = "") -> tuple[str, dict]:
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
            val = params[ph]
            if isinstance(val, list):
                continue  # lists are handled by IN clause expansion below
            bound[ph] = val

    # Default limit
    if "limit" in placeholders and "limit" not in bound:
        bound["limit"] = 50 if intent_name == "destinations_by_country_from_origin" else DEFAULT_LIMIT

    # --- Optional clause appending (mirrors intent notes) ---
    # Clauses are inserted into the WHERE block, before GROUP BY / ORDER BY / LIMIT —
    # never appended to the end of the template (which would place them after ORDER BY).
    note = intent_def.get("note", "")

    if "trip_type" in params and "trip_type" not in placeholders:
        if "trip_type" in note:
            template = _insert_before_group_or_order(template, "AND f.f_trip_type = :trip_type")
            bound["trip_type"] = params["trip_type"]

    if "currency_code" in params and "currency_code" not in placeholders:
        if "currency_code" in note:
            template = _insert_before_group_or_order(template, "AND f.f_currency_code = :currency_code")
            bound["currency_code"] = params["currency_code"]

    if "cabin_class" in params and "cabin_class" not in placeholders:
        if "cabin_class" in note:
            template = _insert_before_group_or_order(template, "AND f.f_cabin_class = :cabin_class")
            bound["cabin_class"] = params["cabin_class"]

    if "max_price" in params and "max_price" not in placeholders:
        if "max_price" in note:
            template = _insert_before_order(template, "HAVING MIN(f.f_total_amount_fare_total) <= :max_price")
            bound["max_price"] = params["max_price"]

    if "day_type" in params and "day_type" not in placeholders:
        if "day_type" in note:
            day_type = str(params["day_type"]).lower()
            if day_type == "weekend":
                template = _insert_before_group_or_order(
                    template,
                    "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) IN (6, 7)",
                )
            elif day_type == "weekday":
                template = _insert_before_group_or_order(
                    template,
                    "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) BETWEEN 1 AND 5",
                )

    # --- destinations_by_duration: dynamic HAVING ---
    if intent_name == "destinations_by_duration" and "HAVING" in template.upper():
        # Strip the hardcoded HAVING clause and rebuild, then re-insert before ORDER BY.
        template = re.sub(r"HAVING\s+.*?(?=\s+ORDER\s+BY|\s+LIMIT\b|$)", "", template, flags=re.IGNORECASE).strip()
        having_clauses = []
        if "max_duration_mins" in params:
            having_clauses.append("MIN(f.f_flight_duration) <= :max_duration_mins")
            bound["max_duration_mins"] = params["max_duration_mins"]
        if "min_duration_mins" in params:
            having_clauses.append("MIN(f.f_flight_duration) >= :min_duration_mins")
            bound["min_duration_mins"] = params["min_duration_mins"]
        if having_clauses:
            template = _insert_before_order(template, "HAVING " + " AND ".join(having_clauses))

    # --- IN clause expansion for hybrid intents ---
    # List params arrive from SPARQL results and must be expanded to individual bindings.
    # Templates may use either  IN :param_name  or  IN (:param_name)
    # Both are normalised to    IN (:item_0, :item_1, ...)
    for list_param, prefix in [
        ("destination_airport_codes", "code"),
        ("aircraft_codes", "ac"),
    ]:
        if list_param not in params:
            continue
        values = params[list_param]
        if isinstance(values, list):
            placeholders_in = "(" + ", ".join(f":{prefix}_{i}" for i in range(len(values))) + ")"
            template = re.sub(
                rf"IN\s+\(:{re.escape(list_param)}\)|IN\s+:{re.escape(list_param)}",
                f"IN {placeholders_in}",
                template,
            )
            for i, v in enumerate(values):
                bound[f"{prefix}_{i}"] = v
            bound.pop(list_param, None)  # remove the list — not a valid sqlite param
        else:
            bound[list_param] = values

    return template, bound
