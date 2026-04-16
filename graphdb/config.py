from pathlib import Path

HERE = Path(__file__).parent          # graphdb/

# ── API Keys ──────────────────────────────────────────────────
GEMINI_API_KEY = ""  # paste your Gemini API key here

SEMANTIC_LAYER = HERE.parent / "resources" / "semantics" / "semantic_layer_v3.json"
PROMPT_TEMPLATE = HERE / "query_plan_prompt.j2"
FACT_CSV = HERE / "csv_files" / "fact_flight_info.csv"

GRAPHDB_URL = "http://localhost:7200/repositories/dataontology"
GRAPHDB_TIMEOUT = 30

DEFAULT_LIMIT = 10
GEMINI_MODEL = "gemini-2.5-flash"

# ── Dev defaults ───────────────────────────────────────────────
# Simulates a logged-in user's passport for visa enrichment in dev/testing.
# IN (India) requires eVisa for Thailand — good for testing visa display.
# Set to None to disable and test the "no passport provided" fallback.
DEV_PASSPORT_COUNTRY = "IN"
