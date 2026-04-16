"""
Dev pipeline — keyboard input → Gemini → validate → route → SPARQL/SQL → output.

Run:
    cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb
    export GEMINI_API_KEY=your_key_here
    python pipeline.py

Mirrors prod pipeline phases from Claude_project_overview.md:
  Phase 1 — LLM intent extraction
  Phase 2 — Route by execution_phase
  Phase 3 — SPARQL execution (SELECT or CONSTRUCT)
  Phase 4 — Conditional visa SELECT
  Phase 5 — SQL execution (SQLite)
  Phase 6 — Response formatting → terminal
"""

from __future__ import annotations

import sys

from config import DEV_PASSPORT_COUNTRY
from compiler import compile_sparql, compile_sql
from db import execute_sql, get_connection
from llm import call_gemini
from loader import build_prompt_context, load_semantics
from response import format_attractions, format_flight_with_destination, format_highlights, format_table, format_vacation_plan
from sparql_exec import check_graphdb, execute_construct, execute_select
from validator import print_query_plan, validate

SPARQL_ONLY_PHASES = ("sparql_only", "sparql_first")
SQL_PHASES = ("sql_first",)
HYBRID_PHASES = ("sparql_then_sql",)


HISTORY_WINDOW = 2  # number of prior exchanges to include in prompt


def run_once(
    question: str,
    semantics: dict,
    intents_str: str,
    param_schema_str: str,
    history: list[tuple[str, dict]] | None = None,
) -> dict | None:
    """Run one question through the pipeline. Returns the query_plan on success, else None."""
    print("\n" + "─" * 60)

    # ── Phase 1: LLM ────────────────────────────────────────────
    print("[Phase 1] LLM intent extraction")
    try:
        query_plan = call_gemini(question, intents_str, param_schema_str, history=history)
    except (ValueError, EnvironmentError) as e:
        print(f"  [ERROR] {e}")
        return None

    print_query_plan(query_plan)

    # Check for missing required params — ask follow-up and stop
    if query_plan.get("missing_params"):
        follow_up = query_plan.get("follow_up_question", "Please provide more information.")
        print(f"\n  Follow-up needed: {follow_up}")
        return query_plan  # still return so history records the partial plan

    # ── Validate ─────────────────────────────────────────────────
    ok, err = validate(query_plan, semantics)
    if not ok:
        print(f"  [VALIDATION ERROR] {err}")
        return

    intent_name = query_plan["intent"]
    params = query_plan.get("parameters", {})
    intent_def = semantics["intents"][intent_name]
    phase = intent_def.get("execution_phase", "sql_first")
    sparql_type = intent_def.get("sparql_type", "select")

    print(f"\n  execution_phase : {phase}")
    print(f"  sparql_type     : {sparql_type}")

    # ── Phase 2: Route ───────────────────────────────────────────
    print("\n[Phase 2] Routing")

    # ── sparql_then_sql (hybrid) ─────────────────────────────────
    if phase in HYBRID_PHASES:
        print("[Phase 3] SPARQL → extract codes → SQL")
        sparql_template = intent_def.get("sparql_template", "")
        sparql_str = compile_sparql(sparql_template, params)
        print(f"  [sparql] Executing SELECT...")
        try:
            sparql_rows = execute_select(sparql_str)
        except ConnectionError as e:
            print(f"  [ERROR] {e}")
            return

        # Extract airport codes from SPARQL result
        binding_cfg = intent_def.get("sparql_result_binding", {})
        var = binding_cfg.get("variable", "airportCode")
        inject_as = binding_cfg.get("inject_as", "destination_airport_codes")
        codes = [r[var] for r in sparql_rows if r.get(var)]
        print(f"  [sparql] {len(codes)} codes → injecting as '{inject_as}'")
        if not codes:
            print("  No matching codes from SPARQL — no SQL to run.")
            return
        params[inject_as] = codes

        print("[Phase 4] SQL execution")
        rows = _run_sql(intent_def, params, intent_name)
        if rows is not None:
            print(format_table(rows, intent_name))
        return

    # ── sql_first ────────────────────────────────────────────────
    if phase in SQL_PHASES:
        print("[Phase 3] SQL execution")
        rows = _run_sql(intent_def, params, intent_name)
        if rows is None:
            return  # error already printed

        # ── Post-SQL destination enrichment ───────────────────────
        destination = params.get("destination") or params.get("destination_airport_code")
        has_triggers = bool(intent_def.get("enrichment_triggers"))
        if rows and destination and has_triggers:
            print("\n[Phase 4] Destination enrichment (SPARQL CONSTRUCT)")
            vp_intent = semantics["intents"].get("destination_vacation_plan", {})
            vp_template = vp_intent.get("sparql_template", "")
            if vp_template:
                enrich_params = {**params, "destination_airport_code": destination}
                sparql_str = compile_sparql(vp_template, enrich_params)
                try:
                    graph = execute_construct(sparql_str)
                    print(f"  [sparql] Graph loaded — {len(graph)} triples")
                except ConnectionError as e:
                    print(f"  [enrichment] GraphDB unavailable — showing flight table only.\n  {e}")
                    print(format_table(rows, intent_name))
                    return

                # Optional visa check
                visa_rows = []
                visa_intent_name = vp_intent.get("visa_enrichment_trigger")
                passport_cc = params.get("passport_country_code") or DEV_PASSPORT_COUNTRY
                if visa_intent_name and passport_cc:
                    print("[Phase 5] Visa SELECT (conditional)")
                    visa_def = semantics["intents"].get(visa_intent_name, {})
                    visa_template = visa_def.get("sparql_template", "")
                    if visa_template:
                        dest_cc = _extract_country_code(graph, destination)
                        if dest_cc:
                            visa_sparql = compile_sparql(visa_template, {
                                "passport_country_code": passport_cc,
                                "destination_country_code": dest_cc,
                            })
                            try:
                                visa_rows = execute_select(visa_sparql)
                            except ConnectionError:
                                pass

                print("\n[Phase 6] Formatting")
                print(format_flight_with_destination(rows, graph, enrich_params, visa_rows))
                return

        # No enrichment — plain table
        print(format_table(rows, intent_name))
        return

    # ── sparql_only / sparql_first ───────────────────────────────
    if phase in SPARQL_ONLY_PHASES:
        sparql_template = intent_def.get("sparql_template", "")
        if not sparql_template:
            print("  [ERROR] No sparql_template defined for this intent.")
            return

        # ── destination_vacation_plan: CONSTRUCT path ─────────────
        if sparql_type == "construct":
            print("[Phase 3] SPARQL CONSTRUCT — full destination subgraph")
            sparql_str = compile_sparql(sparql_template, params)
            print("  [sparql] Executing CONSTRUCT...")
            try:
                graph = execute_construct(sparql_str)
            except ConnectionError as e:
                print(f"  [ERROR] {e}")
                return
            print(f"  [sparql] Graph loaded — {len(graph)} triples")

            # ── Phase 4: Conditional visa SELECT ──────────────────
            visa_rows = []
            visa_intent = intent_def.get("visa_enrichment_trigger")
            passport_cc = params.get("passport_country_code") or DEV_PASSPORT_COUNTRY
            if visa_intent and passport_cc:
                print("[Phase 4] Visa SELECT (conditional)")
                visa_def = semantics["intents"].get(visa_intent, {})
                visa_template = visa_def.get("sparql_template", "")
                if visa_template:
                    # Need destination_country_code — extract from CONSTRUCT graph
                    dest_cc = _extract_country_code(graph, params.get("destination_airport_code", ""))
                    if dest_cc:
                        visa_params = {
                            "passport_country_code": passport_cc,
                            "destination_country_code": dest_cc,
                        }
                        visa_sparql = compile_sparql(visa_template, visa_params)
                        try:
                            visa_rows = execute_select(visa_sparql)
                            print(f"  [visa] {len(visa_rows)} row(s)")
                        except ConnectionError as e:
                            print(f"  [visa] Could not fetch visa data: {e}")
                    else:
                        print("  [visa] Could not extract country code from graph — skipping visa check.")
            else:
                print("[Phase 4] Visa SELECT — skipped (no passport_country_code)")

            # ── Phase 5: Format & print ───────────────────────────
            print("\n[Phase 5] Formatting vacation plan")
            output = format_vacation_plan(graph, params, visa_rows)
            print(output)
            return

        # ── Standard SELECT (sparql_only / sparql_first) ──────────
        print("[Phase 3] SPARQL SELECT")
        sparql_str = compile_sparql(sparql_template, params)
        print("  [sparql] Executing SELECT...")
        try:
            rows = execute_select(sparql_str)
        except ConnectionError as e:
            print(f"  [ERROR] {e}")
            return
        print(f"  [sparql] {len(rows)} row(s)")
        if intent_name == "destination_highlights":
            print(format_highlights(rows, params))
        elif intent_name == "destination_attractions":
            print(format_attractions(rows, params))
        else:
            print(format_table(rows, intent_name))
        return

    print(f"  [ERROR] Unknown execution_phase: '{phase}'")


def _run_sql(intent_def: dict, params: dict, intent_name: str) -> list[dict] | None:
    """Execute SQL and return rows, or None on error. Caller handles formatting."""
    try:
        sql, bound = compile_sql(intent_def, params)
    except ValueError as e:
        print(f"  [SQL COMPILE ERROR] {e}")
        return None

    print(f"  [sql] Query : {sql[:120]}...")
    print(f"  [sql] Params: {bound}")
    print(f"  [sql] Executing...")
    try:
        rows = execute_sql(sql, bound)
    except Exception as e:
        print(f"  [SQL EXECUTE ERROR] {e}")
        return None

    print(f"  [sql] {len(rows)} row(s)")
    return rows


def _extract_country_code(graph, airport_code: str) -> str | None:
    """Walk the CONSTRUCT graph: airport → city → country → countryCode."""
    from rdflib import Namespace
    EX = Namespace("http://dataontology.example/graph/")

    for airport in graph.subjects(EX.prop_airportCode, None):
        val = graph.value(airport, EX.prop_airportCode)
        if val and str(val) == airport_code:
            city = graph.value(airport, EX.prop_inCity)
            if city:
                country = graph.value(city, EX.prop_belongsToCountry)
                if country:
                    cc = graph.value(country, EX.prop_countryCode)
                    return str(cc) if cc else None
    return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  DataOntology Dev Pipeline")
    print("  Type a question or 'quit' to exit")
    print("=" * 60)

    # Startup checks
    print("\n[Startup] Loading semantic layer...")
    semantics = load_semantics()
    intents_str, param_schema_str = build_prompt_context(semantics)
    print(f"  {len(semantics['intents'])} intents loaded from semantic_layer_v3.json")

    print("[Startup] Initialising SQLite...")
    get_connection()  # triggers CSV load

    graphdb_ok = check_graphdb()
    if graphdb_ok:
        print("[Startup] GraphDB reachable at localhost:7200")
    else:
        print("[Startup] WARNING: GraphDB not reachable — SPARQL queries will fail.")
        print("          SQL-only intents will still work.")

    print("\nReady.\n")

    history: list[tuple[str, dict]] = []

    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            sys.exit(0)

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        plan = run_once(question, semantics, intents_str, param_schema_str, history=history)

        # Update rolling context window
        if plan:
            history.append((question, plan))
            if len(history) > HISTORY_WINDOW:
                history.pop(0)


if __name__ == "__main__":
    main()
