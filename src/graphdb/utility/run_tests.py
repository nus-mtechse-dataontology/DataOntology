"""
Test runner — reads csv_files/test_cases.csv, runs pending cases,
writes clean human-readable results back to the CSV, and appends
the full debug output to csv_files/test_run.log.

Run:
    cd /Users/keewenjie/Desktop/NUS/DataOntology/DataOntology/graphdb/utility
    python run_tests.py

CSV columns written by this runner:
  LLM Output    — raw JSON plan returned by Gemini (cached for replay)
  Actual Intent — intent name identified by LLM
  Actual Phase  — execution_phase routed by pipeline
  Response      — clean user-facing output (debug lines stripped)
  Error         — [ERROR] / [EXCEPTION] blocks if any

LLM caching:
  If a case already has "LLM Output" filled, the Gemini call is skipped and
  the cached plan is replayed. This lets you re-run formatting fixes instantly
  without consuming API quota or waiting for the model.

  Output columns (Response, Actual Intent, Actual Phase, Error, and the Pass
  columns) are cleared automatically at the start of every run so every
  execution is a full fresh validation. LLM Output is never cleared.

Validation columns (left blank, filled manually):
  Intent Pass   — did the pipeline identify the right intent?
  Phase Pass    — did it use the right execution path?
  Output Pass   — is the response useful and correct for a real user?

Safety: results are written row-by-row via temp file + atomic rename.
The original CSV is never truncated mid-run.
"""
import csv
import io
import json
import re
import shutil
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent.parent      # graphdb/
TEST_CSV = HERE / "csv_files" / "test_cases.csv"
LOG_FILE = HERE / "csv_files" / "test_run.log"

# ── Bootstrap pipeline ─────────────────────────────────────────────────────────
sys.path.insert(0, str(HERE))

# from db import get_connection
import os
import tomllib
import logging

from graphdb.loader import build_prompt_context, load_semantics
from graphdb.sparql_exec import check_graphdb
from graphdb.pipeline import GraphDbPipeline


from dao.fact_flight_info_dao import FactFlightInfoDAO
from session.db_session import DBSession

DELIMITER = "|"

# Column added by this runner for LLM caching
_LLM_OUTPUT_COL = "LLM Output"

# Lines that are internal pipeline debug output — stripped before writing to CSV.
# Everything that survives this filter is user-facing content.
_DEBUG_RE = re.compile(
    r"^\s*─+\s*$"                                   # ───── dividers
    r"|^\[Phase \d"                                  # [Phase N] headers
    r"|^\s+\[(?:llm|sql|sparql|visa|enrichment)\]"  # subsystem log lines (indented)
    r"|^\[(?:llm|sql|sparql|visa|enrichment)\]"     # subsystem log lines (unindented)
    r"|^\s+Intent\s+:"                               # Intent     : xxx  (print_query_plan)
    r"|^\s+Confidence\s+:"                           # Confidence : xxx
    r"|^\s+Params\s+:"                               # Params     : xxx
    r"|^\s+Missing\s+:"                              # Missing    : xxx
    r"|^\s+Follow-up\s+:"                            # Follow-up  : xxx  (print_query_plan)
    r"|^\s+execution_phase\s"                        # execution_phase : xxx
    r"|^\s+sparql_type\s"                            # sparql_type     : xxx
)


def _load_cases(path: Path) -> tuple[list[dict], list[str]]:
    """Load all rows. Returns (cases, fieldnames). Adds LLM Output column if absent."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=DELIMITER)
        fieldnames = list(reader.fieldnames or [])
        cases = list(reader)

    # Ensure LLM Output column exists — insert it after Actual Phase if not present
    if _LLM_OUTPUT_COL not in fieldnames:
        try:
            insert_after = fieldnames.index("Actual Phase")
        except ValueError:
            insert_after = len(fieldnames) - 1
        fieldnames.insert(insert_after + 1, _LLM_OUTPUT_COL)

    return cases, fieldnames


def _save_cases_safe(path: Path, cases: list[dict], fieldnames: list[str]) -> None:
    """Atomically replace CSV — original survives any write failure."""
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                delimiter=DELIMITER,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(cases)
        shutil.move(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _capture_run(
    question: str,
    semantics: dict,
    intents_str: str,
    param_schema_str: str,
    prefilled_plan: dict | None = None,
) -> tuple[str, dict | None]:
    """
    Run one question through the pipeline.

    Returns (stdout_output, query_plan).
    If prefilled_plan is given, Phase 1 (Gemini) is skipped — pipeline re-runs
    from validation onward using the cached plan.
    """
    buf = io.StringIO()
    plan = None
    with redirect_stdout(buf):
        try:
            plan = GraphDbPipeline().run_once(
                question, semantics, intents_str, param_schema_str,
                history=[], prefilled_plan=prefilled_plan,
            )
        except Exception:
            print(f"[EXCEPTION]\n{traceback.format_exc()}")
    return buf.getvalue(), plan


def _parse_intent(output: str) -> str:
    """Extract intent name from pipeline stdout."""
    m = re.search(r"Intent\s*:\s*(\S+)", output)
    return m.group(1) if m else ""


def _parse_phase(output: str) -> str:
    """Extract execution_phase from pipeline stdout."""
    m = re.search(r"execution_phase\s*:\s*(\S+)", output)
    if m:
        return m.group(1)
    if "Follow-up needed:" in output:
        return "follow_up"
    return ""


def _extract_response(output: str) -> str:
    """Return only user-facing lines from pipeline stdout.

    Strips all internal debug lines (phase headers, subsystem logs, LLM metadata)
    so what remains is the formatted response a real user would see.
    """
    kept = [ln for ln in output.splitlines() if not _DEBUG_RE.match(ln)]
    # Trim leading/trailing blank lines
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def _extract_errors(output: str) -> str:
    """Extract [EXCEPTION] and [ERROR] blocks from pipeline stdout."""
    blocks = re.findall(r"\[(?:EXCEPTION|ERROR)[^\]]*\].*?(?=\n\[|\Z)", output, re.DOTALL)
    return " | ".join(b.strip() for b in blocks) if blocks else ""


def main() -> None:
    print("=" * 60)
    print("  DataOntology Test Runner")
    print("=" * 60)

    # ── Setup ─────────────────────────────────────────────────────
    print("\n[Setup] Loading semantic layer...")
    semantics = load_semantics()
    intents_str, param_schema_str = build_prompt_context(semantics)
    print(f"  {len(semantics['intents'])} intents loaded")

    print("[Setup] Initialising SQLite...")
    # get_connection()

    graphdb_ok = check_graphdb()
    if graphdb_ok:
        print("[Setup] GraphDB reachable")
    else:
        print("[Setup] WARNING: GraphDB not reachable — SPARQL-dependent tests will fail")

    # ── Demo mode — batch execution disabled ──────────────────────
    # To re-enable the full test suite, uncomment the block below.

    # BATCH = None   # set to an int (e.g. 3) to limit cases per run

    # # ── Load cases ────────────────────────────────────────────────
    # cases, fieldnames = _load_cases(TEST_CSV)
    # total = len(cases)
    # print(f"[Setup] Loaded {total} test case(s) from {TEST_CSV.name}")

    # # ── Clear output columns so every run is a full fresh validation ──
    # # LLM Output is preserved so Gemini is skipped on reruns.
    # _OUTPUT_COLS = ("Actual Intent", "Actual Phase", "Response", "Error",
    #                 "Intent Pass", "Phase Pass", "Output Pass")
    # cleared = sum(1 for c in cases if any(c.get(col, "").strip() for col in _OUTPUT_COLS))
    # for c in cases:
    #     for col in _OUTPUT_COLS:
    #         c[col] = ""
    # if cleared:
    #     _save_cases_safe(TEST_CSV, cases, fieldnames)
    #     print(f"[Setup] Cleared output columns for {cleared} case(s)")

    # # All cases are now pending
    # pending = cases
    # batch = pending if BATCH is None else pending[:BATCH]

    # # Count how many will use cached LLM output vs. fresh Gemini call
    # cached_count = sum(1 for c in batch if c.get(_LLM_OUTPUT_COL, "").strip())
    # fresh_count  = len(batch) - cached_count
    # print(
    #     f"[Run]   {len(pending)} pending  |  running {len(batch)} this batch  "
    #     f"({cached_count} cached, {fresh_count} need Gemini)\n"
    # )

    # if not batch:
    #     print("  Nothing to run.")
    #     return

    # # ── Open log ──────────────────────────────────────────────────
    # log_handle = LOG_FILE.open("a", encoding="utf-8")
    # log_handle.write(
    #     f"\n{'='*60}\n"
    #     f"  Test Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    #     f"  Batch: {len(batch)} case(s)  ({cached_count} cached, {fresh_count} fresh)\n"
    #     f"{'='*60}\n"
    # )

    # for case in batch:
    #     tc_id   = case.get("Test ID", "?")
    #     prompt  = case.get("Prompt Entered", "").strip()
    #     cat     = case.get("Category", "")
    #     purpose = case.get("Test Purpose", "")

    #     print(f"  ── {tc_id} : {cat} ──")
    #     print(f"  {purpose}")
    #     print(f"  Prompt : {prompt}")
    #     print()

    #     if not prompt:
    #         case["Response"]        = "SKIPPED — no prompt"
    #         case["Actual Intent"]   = ""
    #         case["Actual Phase"]    = ""
    #         case["Error"]           = ""
    #         case[_LLM_OUTPUT_COL]   = ""
    #         print("  Skipped — no prompt\n")
    #     else:
    #         # Replay cached Gemini plan if available — skip API call
    #         cached_json    = case.get(_LLM_OUTPUT_COL, "").strip()
    #         prefilled_plan = None
    #         if cached_json:
    #             try:
    #                 prefilled_plan = json.loads(cached_json)
    #                 print(f"  [{datetime.now().strftime('%H:%M:%S')}] Replaying cached plan (Gemini skipped)...", file=sys.stderr, flush=True)
    #             except (json.JSONDecodeError, ValueError):
    #                 print(f"  [{datetime.now().strftime('%H:%M:%S')}] Cached plan invalid — calling Gemini...", file=sys.stderr, flush=True)
    #         else:
    #             print(f"  [{datetime.now().strftime('%H:%M:%S')}] Calling Gemini...", file=sys.stderr, flush=True)

    #         raw, plan = _capture_run(prompt, semantics, intents_str, param_schema_str, prefilled_plan)
    #         print(f"  [{datetime.now().strftime('%H:%M:%S')}] Done", file=sys.stderr, flush=True)

    #         case["Actual Intent"]   = _parse_intent(raw)
    #         case["Actual Phase"]    = _parse_phase(raw)
    #         case["Response"]        = _extract_response(raw)
    #         case["Error"]           = _extract_errors(raw)
    #         case["Intent Pass"]     = ""
    #         case["Phase Pass"]      = ""
    #         case["Output Pass"]     = ""

    #         # Save plan to LLM Output column (only if fresh from Gemini — don't overwrite cached)
    #         if plan is not None and not cached_json:
    #             try:
    #                 case[_LLM_OUTPUT_COL] = json.dumps(plan)
    #             except (TypeError, ValueError):
    #                 pass

    #         # Print clean response to terminal too
    #         print(case["Response"])
    #         if case["Error"]:
    #             print(f"\n  [!] Errors captured — see Error column or log.")
    #         cached_label = " [cached]" if prefilled_plan else ""
    #         print(f"\n  ── {tc_id} done{cached_label}. Pending review. ──\n")

    #         # Full debug output to log file
    #         log_handle.write(
    #             f"\n── {tc_id} | {cat} | {purpose}\n"
    #             f"Prompt  : {prompt}\n"
    #             f"Intent  : {case['Actual Intent']}  |  Phase : {case['Actual Phase']}\n"
    #             f"Cached  : {'yes' if prefilled_plan else 'no'}\n"
    #         )
    #         if case["Error"]:
    #             log_handle.write(f"Errors  : {case['Error']}\n")
    #         log_handle.write(f"\n--- Response ---\n{case['Response']}\n")
    #         log_handle.write(f"\n--- Full Debug ---\n{raw}\n")
    #         log_handle.flush()

    #     # Save after every case so a crash can't lose prior results
    #     _save_cases_safe(TEST_CSV, cases, fieldnames)

    # log_handle.write(
    #     f"\n{'='*60}\n"
    #     f"  {len(batch)} case(s) complete\n"
    #     f"{'='*60}\n"
    # )
    # log_handle.close()

    # print("=" * 60)
    # print(f"  CSV  → {TEST_CSV}")
    # print(f"  Log  → {LOG_FILE}")
    # print(f"  Done : {len(batch)} case(s) run")
    # print("=" * 60)

    # ── Interactive demo mode ──────────────────────────────────────
    print("\n[Demo] Pipeline ready. Type a query and press Enter (Ctrl+C to quit).\n")
    while True:
        try:
            question = input("Query> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Demo] Exiting.")
            break
        if not question:
            continue
        raw, _ = _capture_run(question, semantics, intents_str, param_schema_str)
        response = _extract_response(raw)
        print(f"\n{response}\n")


def load_config() -> dict:
    """
    Loads the config for the named ingestion.
    """
    with open(Path(os.getenv("PROJECT_PATH", ""), "resources", "config.toml")) as cf:
        try:
            return tomllib.loads(cf.read())
        
        except tomllib.TOMLDecodeError as exc:
            logger.error("Startup: error while loading config, %s", exc)
            logger.error(traceback.format_exc())
            raise exc


if __name__ == "__main__":
    os.environ["PROJECT_PATH"] = str(Path(__file__).resolve().parents[3])
    logger = logging.getLogger("data_ontology")
    config = load_config()
    session = DBSession(config)
    fact_flight_info_dao = FactFlightInfoDAO(session.engine)
    main()
