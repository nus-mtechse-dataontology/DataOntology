"""
Smoke test for GraphDBService integration.
Run this from the DataOntology project root:
    python graphdb/smoke_test.py
"""

import sys
from pathlib import Path

# Ensure project root and graphdb/ are both on the path
_project_root = str(Path(__file__).resolve().parents[1])
_graphdb_dir = str(Path(__file__).resolve().parent)

for p in [_project_root, _graphdb_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

print("=== GraphDB Smoke Test ===\n")

# ── 1. Import check ──────────────────────────────────────────────────────────
print("[1] Importing GraphDBService...", end=" ", flush=True)
try:
    from graphdb.service import GraphDBService
    print("OK")
except Exception as e:
    print(f"FAIL\n    {e}")
    sys.exit(1)

# ── 2. Init check ────────────────────────────────────────────────────────────
print("[2] Initialising GraphDBService...", end=" ", flush=True)
try:
    svc = GraphDBService()
    print("OK")
except Exception as e:
    print(f"FAIL\n    {e}")
    sys.exit(1)

# ── 3. Reachability check ────────────────────────────────────────────────────
print("[3] Checking GraphDB reachability...", end=" ", flush=True)
try:
    reachable = svc.graphdb_reachable()
    print(f"{'REACHABLE' if reachable else 'NOT REACHABLE (SPARQL intents will fail)'}")
except AttributeError:
    print("SKIP (graphdb_reachable() not present)")

# ── 4. Query check ───────────────────────────────────────────────────────────
QUESTIONS = [
    "do singaporeans need a visa for australia?",
    "what flights go to tokyo?",
    "what is the weather like in london?",
]

print("\n[4] Running sample queries:")
for q in QUESTIONS:
    print(f"\n  Q: {q}")
    try:
        result = svc.ask(q)
        if result is not None:
            print(f"  A (graphdb handled):\n{result}")
        else:
            print("  → graphdb returned None — would fall through to orchestrator")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n=== Smoke test complete ===")
