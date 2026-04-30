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

import re
import sys

def _eprint(*args, **kwargs):
    """Print to stderr so debug lines never reach the user-facing output."""
    print(*args, file=sys.stderr, **kwargs)
from gcompiler import compile_sparql, compile_sql
from db import execute_sql, get_connection
from llm import call_gemini
from loader import build_prompt_context, load_semantics
from response import (
    format_aircraft_on_route, format_airlines_on_route, format_amenities,
    format_airport_info, format_airports_in_city, format_airports_with_amenity,
    format_attractions, format_best_months, format_cheapest_month,
    format_cities_in_country, format_country_info,
    format_currency_list, format_cuisines, format_departures,
    format_destination_currency, format_destinations_by_season, format_exchange_rate,
    format_festivals, format_festivals_by_month, format_festivals_by_type,
    format_flight_count, format_flight_with_destination,
    format_good_weather_destinations, format_highlights, format_language,
    format_language_destinations, format_neighborhoods, format_overview,
    format_route_list, format_route_statistics, format_safe_destinations,
    format_safety, format_solo_female_destinations, format_table,
    format_timezone, format_transport, format_transit_route, format_travel_styles,
    format_vacation_plan, format_visa_check, format_visa_duration,
    format_visa_list, format_weather,
)
from sparql_exec import check_graphdb, execute_construct, execute_select
from validator import print_query_plan, validate

SPARQL_ONLY_PHASES = ("sparql_only", "sparql_first")
SQL_PHASES = ("sql_first",)
HYBRID_PHASES = ("sparql_then_sql",)

# Maps raw SQL column names → user-friendly table headers
_COLUMN_RENAMES = {
    "f_currency_code": "currency",
    "min_duration_mins": "min_duration",
    "flight_count": "flights",
    "first_departure": "first_dep",
}


def _friendly_columns(rows: list[dict]) -> list[dict]:
    """Return a copy of rows with internal column names replaced by friendly labels."""
    if not rows:
        return rows
    return [{_COLUMN_RENAMES.get(k, k): v for k, v in row.items()} for row in rows]


HISTORY_WINDOW = 2  # number of prior exchanges to include in prompt

_MONTH_NAMES_FULL = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]

def _humanise_follow_up_dates(text: str) -> str:
    """Replace ISO dates with human-readable format and add month-level hint for date requests."""
    def _replace(m):
        try:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{_MONTH_NAMES_FULL[mo - 1]} {d}, {y}"
        except Exception:
            return m.group(0)
    text = re.sub(r"(\d{4})-(\d{2})-(\d{2})", _replace, text)
    # NEW-I: if follow-up is asking for a date, add month-level hint
    if re.search(r"\bdate\b", text, re.IGNORECASE) and "(e.g." not in text:
        text = text.rstrip("?. ") + " (e.g. June, or a specific date like 15 June 2026)"
    return text


def run_once(
    question: str,
    semantics: dict,
    intents_str: str,
    param_schema_str: str,
    history: list[tuple[str, dict]] | None = None,
    prefilled_plan: dict | None = None,
) -> dict | None:
    """
    Run one question through the pipeline. Returns the query_plan on success, else None.

    If prefilled_plan is provided, Phase 1 (Gemini) is skipped and the cached plan
    is used directly — useful for re-running formatting fixes without API calls.
    """
    print("\n" + "─" * 60)

    # ── Phase 1: LLM ────────────────────────────────────────────
    print("[Phase 1] LLM intent extraction")
    if prefilled_plan is not None:
        query_plan = prefilled_plan
        print("  [llm] Using cached plan — Gemini skipped")
    else:
        try:
            query_plan = call_gemini(question, intents_str, param_schema_str, history=history)
        except (ValueError, EnvironmentError) as e:
            print(f"  [ERROR] {e}")
            return None
        except Exception as e:
            _eprint(f"  [LLM EXCEPTION] {e}")
            print("Sorry, I'm having trouble connecting right now. Please try again in a moment.")
            return None

    # Guard: LLM returned a list (multi-leg query) — not supported
    if isinstance(query_plan, list):
        print(
            "\n  I can only look up one flight at a time.\n"
            "  Please ask about each leg separately,\n"
            "  e.g. 'Cheapest flight from FRA to MEL on 3 June 2026'"
        )
        return None

    print_query_plan(query_plan)

    # Check for missing required params — reject incomplete query, no follow-up
    if query_plan.get("missing_params"):
        missing = ", ".join(query_plan["missing_params"])
        print(
            f"\n  Your query is missing: {missing}."
            "\n  Please include all details in one query."
            "\n  e.g. 'Cheapest flight from SIN to BKK in May'"
        )
        return None

    # ── Validate ─────────────────────────────────────────────────
    ok, err = validate(query_plan, semantics)
    if not ok:
        if "Unknown intent" in err:
            print(
                "\n  I can help with flight searches, visa information, and destination guides.\n"
                "  Try: 'Cheapest flight from SIN to BKK in June', 'Tell me about Bangkok',\n"
                "  or 'Do I need a visa for Japan?'"
            )
        else:
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
        # NEW-H: SQL step needs :origin — reject if missing, no follow-up
        sql_template = intent_def.get("sql_template", "")
        if ":origin" in sql_template and not params.get("origin"):
            print(
                "\n  Your query is missing: origin airport."
                "\n  Please include all details in one query."
                "\n  e.g. 'Destinations from SIN with metro transport'"
            )
            return None

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
            # M9: include the filter value so user knows what wasn't found
            filter_val = (params.get("travel_style") or params.get("attraction_type")
                          or params.get("transport_mode") or params.get("safety_tier")
                          or params.get("festival_type") or "")
            filter_str = (f" matching '{filter_val.replace('_', ' ')}'" if filter_val else "")
            print(
                f"\n  No destinations{filter_str} found."
                " Try a different filter or ask about flights from SIN."
            )
            return query_plan
        params[inject_as] = codes

        print("[Phase 4] SQL execution")
        rows = _run_sql(intent_def, params, intent_name)
        if rows is not None:
            _enrich_destination_names(rows)
            print(format_table(_friendly_columns(rows), intent_name, params))
        return query_plan

    # ── sql_first ────────────────────────────────────────────────
    if phase in SQL_PHASES:
        print("[Phase 3] SQL execution")
        rows = _run_sql(intent_def, params, intent_name)
        if rows is None:
            return  # error already printed
        _enrich_destination_names(rows)

        # ── Friendly empty-result messages before formatter dispatch ──
        if not rows:
            if params.get("trip_type") == "R":
                print(
                    "\n  Return flight pricing is not currently in our dataset — all fares are one-way."
                    "\n  Try the same question without specifying a return trip."
                )
                return query_plan
            if _is_date_out_of_range(params):
                print(
                    "\n  Flight data is currently available for January to August 2026."
                    "\n  No data for September onwards yet — check back closer to your travel date."
                )
                return query_plan
            # Transit fallback: no direct flight — try connecting routes (min 2h layover)
            if intent_name in ("cheapest_flight_on_route", "flights_on_date", "next_available_flight"):
                transit_def = semantics["intents"].get("cheapest_transit_route", {})
                if transit_def:
                    print("  [transit] No direct flight — trying connecting routes...")
                    # Normalise date params: flights_on_date uses departure_date; transit needs start_date/end_date
                    transit_params = dict(params)
                    if "departure_date" in transit_params and "start_date" not in transit_params:
                        d = str(transit_params["departure_date"]).split("T")[0]
                        transit_params["start_date"] = d
                        transit_params["end_date"] = d
                    transit_rows = _run_sql(transit_def, transit_params, "cheapest_transit_route")
                    if transit_rows:
                        print(format_transit_route(transit_rows, params))
                        return query_plan
            print("\n  No flights found for that route and date.\n")
            return query_plan

        # ── Dedicated formatters for aggregate intents ────────────
        if intent_name == "cheapest_month_for_route":
            print(format_cheapest_month(rows, params))
            return query_plan
        if intent_name == "airlines_on_route":
            print(format_airlines_on_route(rows, params))
            return query_plan
        if intent_name == "route_statistics":
            print(format_route_statistics(rows, params))
            return query_plan
        if intent_name == "all_flights_on_date":
            _enrich_destination_names(rows)
            print(format_departures(rows, params))
            return query_plan
        if intent_name == "flight_count_on_route":
            print(format_flight_count(rows, params))
            return query_plan
        if intent_name == "aircraft_on_route":
            print(format_aircraft_on_route(rows, params))
            return query_plan
        if intent_name == "cheapest_transit_route":
            print(format_transit_route(rows, params))
            return query_plan

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
                    print(format_table(_friendly_columns(rows), intent_name))
                    return

                # Optional visa check
                visa_rows = []
                visa_intent_name = vp_intent.get("visa_enrichment_trigger")
                passport_cc = params.get("passport_country_code")
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
                print(format_flight_with_destination(rows, graph, enrich_params, visa_rows, intent_name))
                return query_plan

        # No enrichment — plain table
        print(format_table(_friendly_columns(rows), intent_name, params))
        return query_plan

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
            passport_cc = params.get("passport_country_code")
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
            return query_plan

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
        # H2/L1/L8: resolve city name for all enrichment formatters
        params = _inject_city_name(params)
        if intent_name == "destination_highlights":
            # M10: enrich params with city_name so formatter shows "Tokyo" not "NRT"
            code = params.get("destination_airport_code", "")
            if code:
                name_map = _resolve_airport_names([code])
                if name_map.get(code):
                    city_only = name_map[code].split(",")[0].strip()
                    params = {**params, "city_name": city_only}
            print(format_highlights(rows, params))
        elif intent_name == "destination_attractions":
            print(format_attractions(rows, params))
        elif intent_name == "visa_destinations_by_policy":
            print(format_visa_list(rows, params))
        elif intent_name == "destination_weather_by_month":
            print(format_weather(rows, params))
        elif intent_name == "destination_festivals":
            print(format_festivals(rows, params))
        elif intent_name == "destination_transport":
            print(format_transport(rows, params))
        elif intent_name == "destination_cuisines":
            print(format_cuisines(rows, params))
        elif intent_name == "destination_language":
            print(format_language(rows, params))
        elif intent_name == "destination_timezone":
            print(format_timezone(rows, params))
        elif intent_name == "destination_currency":
            print(format_destination_currency(rows, params))
        elif intent_name == "airport_amenities":
            print(format_amenities(rows, params))
        elif intent_name == "destination_safety":
            print(format_safety(rows, params))
        elif intent_name == "destination_neighborhoods":
            print(format_neighborhoods(rows, params))
        elif intent_name == "destination_overview":
            print(format_overview(rows, params))
        elif intent_name == "destination_travel_styles":
            print(format_travel_styles(rows, params))
        elif intent_name == "best_months_to_visit":
            print(format_best_months(rows, params))
        elif intent_name in ("all_routes_from_origin", "routes_by_airline", "airlines_covering_route",
                             "routes_from_origin_by_country"):
            print(format_route_list(rows, params, intent_name))
        elif intent_name == "currencies_by_region":
            print(format_currency_list(rows, params))
        elif intent_name in ("visa_check_for_destination", "visa_required_destinations"):
            print(format_visa_check(rows, params) if intent_name == "visa_check_for_destination" else format_visa_list(rows, params))
        elif intent_name == "airports_in_city":
            print(format_airports_in_city(rows, params))
        elif intent_name == "destinations_by_language":
            print(format_language_destinations(rows, params))
        elif intent_name == "destinations_with_festivals_in_month":
            print(format_festivals_by_month(rows, params))
        elif intent_name == "cities_in_country":
            print(format_cities_in_country(rows, params))
        elif intent_name == "country_info":
            print(format_country_info(rows, params))
        elif intent_name == "destinations_solo_female_friendly":
            print(format_solo_female_destinations(rows, params))
        elif intent_name == "currency_exchange_rate":
            print(format_exchange_rate(rows, params))
        elif intent_name == "visa_duration_check":
            print(format_visa_duration(rows, params))
        elif intent_name == "airports_with_amenity":
            print(format_airports_with_amenity(rows, params))
        elif intent_name == "safe_destinations_list":
            print(format_safe_destinations(rows, params))
        elif intent_name == "festivals_by_type_global":
            print(format_festivals_by_type(rows, params))
        elif intent_name == "airport_info":
            print(format_airport_info(rows, params))
        elif intent_name == "destinations_by_season":
            print(format_destinations_by_season(rows, params))
        elif intent_name == "destinations_good_weather_in_month":
            print(format_good_weather_destinations(rows, params))
        else:
            print(format_table(_friendly_columns(rows), intent_name, params))
        return query_plan

    print(f"  [ERROR] Unknown execution_phase: '{phase}'")


# Fact table covers Jan–Aug 2026
_DATA_END = (2026, 8)


def _is_date_out_of_range(params: dict) -> bool:
    """Return True when any date param is beyond the available data window."""
    for key in ("departure_date", "start_date", "end_date", "date"):
        val = str(params.get(key) or "")
        if len(val) >= 7:
            try:
                year, month = int(val[:4]), int(val[5:7])
                if (year, month) > _DATA_END:
                    return True
            except (ValueError, IndexError):
                pass
    return False


def _run_sql(intent_def: dict, params: dict, intent_name: str) -> list[dict] | None:
    """Execute SQL and return rows, or None on error. Caller handles formatting."""
    try:
        sql, bound = compile_sql(intent_def, params, intent_name)
    except ValueError as e:
        print(f"  [SQL COMPILE ERROR] {e}")
        return None

    print(f"  [sql] Query : {sql[:120]}...")
    print(f"  [sql] Params: {bound}")
    print(f"  [sql] Executing...")
    try:
        rows = execute_sql(sql, bound)
    except Exception as e:
        err_str = str(e)
        if "binding parameter" in err_str or "supply a value" in err_str:
            print(
                "\n  Couldn't complete that query — a required field is missing."
                " Try including the departure airport (e.g. 'from SIN') in your question."
            )
        else:
            print(f"  [SQL EXECUTE ERROR] {e}")
        return None

    print(f"  [sql] {len(rows)} row(s)")
    return rows


def _resolve_airport_names(codes: list[str]) -> dict[str, str]:
    """SPARQL lookup: returns {airportCode: 'City, Country'} for given codes."""
    if not codes:
        return {}
    values = " ".join(f'"{c}"' for c in codes)
    sparql = (
        "PREFIX ex: <http://dataontology.example/graph/> "
        f"SELECT DISTINCT ?airportCode ?cityName ?countryName WHERE {{ "
        f"VALUES ?airportCode {{ {values} }} "
        "?airport a ex:Airport ; ex:prop_airportCode ?airportCode ; ex:prop_inCity ?city . "
        "?city ex:prop_cityName ?cityName ; ex:prop_belongsToCountry ?country . "
        "?country ex:prop_countryName ?countryName . }"
    )
    try:
        rows = execute_select(sparql)
        return {
            r["airportCode"]: f"{r.get('cityName', '')}, {r.get('countryName', '')}".strip(", ")
            for r in rows if r.get("airportCode")
        }
    except Exception as e:
        _eprint(f"  [enrich] SPARQL lookup failed: {e}")
        return {}


def _enrich_destination_names(rows: list[dict]) -> None:
    """In-place: replaces raw airport codes in 'destination' column with 'City, Country (CODE)'."""
    if not rows or "destination" not in rows[0]:
        return
    codes = list({r["destination"] for r in rows if r.get("destination")})
    _eprint(f"  [enrich] Resolving {len(codes)} destination code(s) via SPARQL...")
    name_map = _resolve_airport_names(codes)
    if not name_map:
        _eprint("  [enrich] WARNING: name resolution returned empty — codes will remain raw.")
        return
    resolved = 0
    for row in rows:
        code = row.get("destination", "")
        if code and code in name_map:
            row["destination"] = f"{name_map[code]} ({code})"
            resolved += 1
    _eprint(f"  [enrich] {resolved}/{len(codes)} code(s) resolved.")


def _inject_city_name(params: dict) -> dict:
    """H2/L1/L8: Look up city name for destination_airport_code and inject as city_name."""
    code = params.get("destination_airport_code", "")
    if code and not params.get("city_name"):
        name_map = _resolve_airport_names([code])
        if name_map.get(code):
            city_only = name_map[code].split(",")[0].strip()
            return {**params, "city_name": city_only}
    return params


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

    print("[Startup] Connecting to PostgreSQL...")
    get_connection()

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
