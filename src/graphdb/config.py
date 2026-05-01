from pathlib import Path

GRAPHDB_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]

# ── API Keys ──────────────────────────────────────────────────
GEMINI_API_KEY = ""  # paste your Gemini API key here

SEMANTIC_LAYER = REPO_ROOT / "resources" / "semantics" / "semantic_layer_v3.json"
PROMPT_TEMPLATE = GRAPHDB_DIR / "query_plan_prompt.j2"
FACT_CSV = GRAPHDB_DIR / "csv_files" / "fact_flight_info.csv"

GRAPHDB_URL = "http://localhost:7200/repositories/dataontology"
GRAPHDB_TIMEOUT = 30

DEFAULT_LIMIT = 10
GEMINI_MODEL = "gemma-4-31b-it"
