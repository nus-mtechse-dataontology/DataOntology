"""
Test runner — reads tmp/test_cases.csv, runs the next pending case,
captures full stdout, parses intent + phase, and saves them.
Intent Pass / Phase Pass / Output Pass are left blank for Claude to review.

Run once per test:
    cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb/utility
    python run_tests.py

Validation is NOT automatic.
Claude reads Actual Intent, Actual Phase, and Actual Output and fills:
  Intent Pass  — did the pipeline identify the right intent?
  Phase Pass   — did it use the right execution path?
  Output Pass  — is the response useful and appropriate for a real user?
"""

from __future__ import annotations

import csv
import io
import re
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent.parent      # graphdb/
TEST_CSV = HERE / "csv_files" / "test_cases.csv"

# ── Bootstrap pipeline ────────────────────────────────────────────────────────
sys.path.insert(0, str(HERE))  # graphdb/ — where pipeline.py and all modules live

from compiler import compile_sparql, compile_sql
from db import execute_sql, get_connection
from llm import call_gemini
from loader import build_prompt_context, load_semantics
from response import format_attractions, format_flight_with_destination, format_table, format_vacation_plan
from sparql_exec import check_graphdb, execute_construct, execute_select
from validator import validate
from pipeline import run_once, HISTORY_WINDOW

DELIMITER = "|"


def _load_cases(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=DELIMITER))


def _save_cases(path: Path, cases: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=DELIMITER)
        writer.writeheader()
        writer.writerows(cases)


def _capture_run(question: str, semantics: dict, intents_str: str, param_schema_str: str) -> str:
    """Run one question and return everything printed to stdout."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            run_once(question, semantics, intents_str, param_schema_str, history=[])
        except Exception:
            print(f"[EXCEPTION]\n{traceback.format_exc()}")
    return buf.getvalue()


def _parse_intent(output: str) -> str:
    """Extract intent name from pipeline stdout."""
    m = re.search(r"Intent\s*:\s*(\S+)", output)
    return m.group(1) if m else ""


def _parse_phase(output: str) -> str:
    """Extract execution_phase from pipeline stdout."""
    m = re.search(r"execution_phase\s*:\s*(\S+)", output)
    return m.group(1) if m else ""


def main() -> None:
    print("=" * 60)
    print("  DataOntology Test Runner")
    print("=" * 60)

    # ── Load pipeline dependencies ────────────────────────────────
    print("\n[Setup] Loading semantic layer...")
    semantics = load_semantics()
    intents_str, param_schema_str = build_prompt_context(semantics)
    print(f"  {len(semantics['intents'])} intents loaded")

    print("[Setup] Initialising SQLite...")
    get_connection()

    graphdb_ok = check_graphdb()
    if graphdb_ok:
        print("[Setup] GraphDB reachable")
    else:
        print("[Setup] WARNING: GraphDB not reachable — SPARQL-dependent tests will fail")

    BATCH = 1  # cases to run per invocation

    # ── Load test cases ───────────────────────────────────────────
    cases = _load_cases(TEST_CSV)
    fieldnames = list(cases[0].keys())
    total = len(cases)

    # Queue: rows where all 3 validation columns are blank — skip fully reviewed rows
    def _pending(c: dict) -> bool:
        return not any(c.get(col, "").strip() for col in ("Intent Pass", "Phase Pass", "Output Pass"))

    queue = [c for c in cases if _pending(c)]

    if not queue:
        print(f"\n  All {total} test case(s) reviewed. Nothing left to run.\n")
        return

    batch = queue[:BATCH]
    reviewed = total - len(queue)
    print(f"\n[Run] {len(batch)} case(s) this run  |  {reviewed}/{total} already reviewed\n")

    for case in batch:
        tc_id = case.get("Test ID", "?")
        prompt = case.get("Prompt Entered", "").strip()

        print(f"  ── {tc_id} : {case.get('Category', '')} ──")
        print(f"  {case.get('Test Purpose', '')}")
        print(f"  Prompt : {prompt}")
        print()

        if not prompt:
            case["Actual Output"] = "SKIPPED — no prompt"
            case["Actual Intent"] = ""
            case["Actual Phase"] = ""
            print(f"  Skipped — no prompt\n")
        else:
            actual = _capture_run(prompt, semantics, intents_str, param_schema_str)
            case["Actual Intent"] = _parse_intent(actual)
            case["Actual Phase"] = _parse_phase(actual)
            case["Actual Output"] = " ".join(actual.split())  # whitespace normalised, full output
            # Validation columns left blank for Claude
            case["Intent Pass"] = ""
            case["Phase Pass"] = ""
            case["Output Pass"] = ""

            print(actual)
            print(f"  ── Captured. Pending Claude review. ──\n")

    # ── Write results back ────────────────────────────────────────
    _save_cases(TEST_CSV, cases, fieldnames)

    still_pending = len([c for c in cases if _pending(c)])
    print("=" * 60)
    print(f"  Saved to {TEST_CSV.name}  |  {still_pending} case(s) still pending review")
    print("=" * 60)


if __name__ == "__main__":
    main()
