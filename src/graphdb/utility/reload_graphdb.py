"""
Full GraphDB reload — one command to rebuild and reload everything.

Usage:
    cd /Users/keewenjie/Desktop/NUS/DataOntology/graphdb/utility
    python reload_graphdb.py

Steps:
    1. Run graphdb/build_graphdb_ttl.py  → regenerate DDL + DML from tmp/dim_*.csv
    2. Check GraphDB is reachable at localhost:7200
    3. Create the 'dataontology' repository if it doesn't exist
    4. Clear all existing triples (clean slate)
    5. POST data_ontology_ddl.ttl  (schema)
    6. POST data_ontology_dml.ttl  (instance data — ~68k triples, may take 30s)
    7. Verify triple count
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent.parent      # graphdb/
ROOT = HERE.parent                        # workspace root
DDL_FILE = HERE / "data_ontology_ddl.ttl"
DML_FILE = HERE / "data_ontology_dml.ttl"

GRAPHDB_BASE = "http://localhost:7200"
REPO_ID = "dataontology"
STATEMENTS_URL = f"{GRAPHDB_BASE}/repositories/{REPO_ID}/statements"
REPO_URL = f"{GRAPHDB_BASE}/repositories/{REPO_ID}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(url: str, accept: str = "application/json") -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def _post_ttl(path: Path) -> None:
    print(f"  Uploading {path.name} ({path.stat().st_size:,} bytes)...")
    req = urllib.request.Request(
        STATEMENTS_URL,
        data=path.read_bytes(),
        method="POST",
        headers={"Content-Type": "text/turtle; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            print(f"  Done — HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        sys.exit(1)


def _clear_repo() -> None:
    req = urllib.request.Request(STATEMENTS_URL, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"  Cleared — HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] Clear failed — HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
        sys.exit(1)


def _triple_count() -> int:
    sparql = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
    url = f"{REPO_URL}?query={urllib.parse.quote(sparql)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return int(data["results"]["bindings"][0]["n"]["value"])


# ── Repository creation (3 strategies for GraphDB 9/10/11 compatibility) ──────

def _p(name: str, label: str, value: str) -> dict:
    return {"name": name, "label": label, "value": value}


def _try_create_json(body: bytes) -> bool:
    req = urllib.request.Request(
        f"{GRAPHDB_BASE}/rest/repositories",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  Repository created — HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("  Repository already exists — skipping create.")
            return True
        print(f"  [strategy failed] HTTP {e.code}: {e.read().decode(errors='replace')[:120]}")
        return False


def _try_create_raw(body: bytes, content_type: str) -> bool:
    req = urllib.request.Request(
        f"{GRAPHDB_BASE}/rest/repositories",
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  Repository created — HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("  Repository already exists — skipping create.")
            return True
        print(f"  [strategy failed] HTTP {e.code}: {e.read().decode(errors='replace')[:120]}")
        return False


def _repo_exists() -> bool:
    """Return True if the repository already exists in GraphDB."""
    try:
        data = _get(f"{GRAPHDB_BASE}/rest/repositories")
        repos = json.loads(data)
        return any(r.get("id") == REPO_ID for r in repos)
    except Exception:
        return False


def _ensure_repo() -> None:
    # Short-circuit if repo already exists
    if _repo_exists():
        print("  Repository already exists — skipping create.")
        return

    # Strategy 1 — GraphDB 11.x full param JSON
    config_v11 = {
        "id": REPO_ID, "type": "graphdb", "title": "DataOntology",
        "params": {
            "id":                                  _p("id", "Repository ID", REPO_ID),
            "title":                               _p("title", "Repository description", "DataOntology"),
            "ruleset":                             _p("ruleset", "Ruleset", "rdfsplus-optimized"),
            "storageFolder":                       _p("storageFolder", "Storage folder", "storage"),
            "repositoryType":                      _p("repositoryType", "Repository type", "file-repository"),
            "baseURL":                             _p("baseURL", "Base URL", "http://example.org/owlim#"),
            "defaultNS":                           _p("defaultNS", "Default namespaces for imports(';' delimited)", ""),
            "imports":                             _p("imports", "Imported RDF files(';' delimited)", ""),
            "entityIndexSize":                     _p("entityIndexSize", "Entity index size", "10000000"),
            "entityIdSize":                        _p("entityIdSize", "Entity ID size", "32"),
            "enableContextIndex":                  _p("enableContextIndex", "Enable context index", "false"),
            "enablePredicateList":                 _p("enablePredicateList", "Enable predicate list index", "true"),
            "enableLiteralIndex":                  _p("enableLiteralIndex", "Enable literal index", "true"),
            "enableFtsIndex":                      _p("enableFtsIndex", "Enable full-text search (FTS) index", "false"),
            "ftsIndexes":                          _p("ftsIndexes", "FTS indexes to build (comma delimited)", "default, iri"),
            "ftsStringLiteralsIndex":              _p("ftsStringLiteralsIndex", "FTS index for xsd:string literals", "default"),
            "ftsIrisIndex":                        _p("ftsIrisIndex", "FTS index for full-text indexing of IRIs", "none"),
            "queryTimeout":                        _p("queryTimeout", "Query timeout (seconds)", "0"),
            "queryLimitResults":                   _p("queryLimitResults", "Limit query results", "0"),
            "throwQueryEvaluationExceptionOnTimeout": _p("throwQueryEvaluationExceptionOnTimeout", "Throw exception on query timeout", "false"),
            "readOnly":                            _p("readOnly", "Read-only", "false"),
            "disableSameAs":                       _p("disableSameAs", "Disable owl:sameAs", "true"),
            "rdfsSubClassReasoning":               _p("rdfsSubClassReasoning", "RDFS subClass reasoning", "true"),
            "inMemoryLiteralProperties":           _p("inMemoryLiteralProperties", "Cache literal language tags", "true"),
            "cacheSelectNodes":                    _p("cacheSelectNodes", "Cache select nodes", "true"),
            "checkForInconsistencies":             _p("checkForInconsistencies", "Enable consistency checks", "false"),
            "isShacl":                             _p("isShacl", "Enable SHACL validation", "false"),
            "validationEnabled":                   _p("validationEnabled", "Enable the SHACL validation", "true"),
            "parallelValidation":                  _p("parallelValidation", "Run parallel validation", "true"),
            "shapesGraph":                         _p("shapesGraph", "Named graphs for SHACL shapes", "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph"),
            "validationResultsLimitPerConstraint": _p("validationResultsLimitPerConstraint", "Validation results limit per constraint", "1000"),
            "validationResultsLimitTotal":         _p("validationResultsLimitTotal", "Validation results limit total", "1000000"),
            "transactionalValidationLimit":        _p("transactionalValidationLimit", "Transactional validation limit", "500000"),
            "logValidationPlans":                  _p("logValidationPlans", "Log the executed validation plans", "false"),
            "logValidationViolations":             _p("logValidationViolations", "Log validation violations", "false"),
            "globalLogValidationExecution":        _p("globalLogValidationExecution", "Log every execution step of the SHACL validation", "false"),
            "performanceLogging":                  _p("performanceLogging", "Log the execution time per shape", "false"),
            "dashDataShapes":                      _p("dashDataShapes", "DASH data shapes extensions", "true"),
            "eclipseRdf4jShaclExtensions":         _p("eclipseRdf4jShaclExtensions", "RDF4J SHACL extensions", "true"),
        },
    }
    if _try_create_json(json.dumps(config_v11).encode()):
        return

    # Strategy 2 — GraphDB 9/10.x minimal JSON
    config_v9 = {
        "id": REPO_ID, "type": "free", "title": "DataOntology",
        "params": {
            "ruleset": {"name": "ruleset", "label": "Ruleset", "value": "rdfsplus-optimized"},
        },
    }
    if _try_create_json(json.dumps(config_v9).encode()):
        return

    # Strategy 3 — Turtle config via multipart/form-data
    ttl_config = f"""\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rep:  <http://www.openrdf.org/config/repository#> .
@prefix sr:   <http://www.openrdf.org/config/repository/sail#> .
@prefix sail: <http://www.openrdf.org/config/sail#> .
@prefix owlim: <http://www.ontotext.com/trree/owlim#> .

[] a rep:Repository ;
   rep:repositoryID "{REPO_ID}" ;
   rdfs:label "DataOntology" ;
   rep:repositoryImpl [
      rep:repositoryType "graphdb:FreeSailRepository" ;
      sr:sailImpl [
         sail:sailType "graphdb:FreeSail" ;
         owlim:ruleset "rdfsplus-optimized" ;
         owlim:repository-type "file-repository" ;
         owlim:storage-folder "storage" ;
         owlim:enable-context-index "true" ;
         owlim:enablePredicateList "true" ;
         owlim:disable-sameAs "true" ;
         owlim:query-timeout "0" ;
         owlim:read-only "false"
      ]
   ] .
""".encode()
    boundary = "GraphDBLoaderBoundary"
    multipart = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="config"; filename="repo-config.ttl"\r\n'
        f"Content-Type: text/turtle\r\n\r\n"
    ).encode() + ttl_config + f"\r\n--{boundary}--\r\n".encode()
    if _try_create_raw(multipart, f"multipart/form-data; boundary={boundary}"):
        return

    print("  [ERROR] All repository creation strategies failed.")
    sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  GraphDB Full Reload")
    print("=" * 60)

    # Step 1 — Rebuild TTLs from CSVs
    print("\n[1] Rebuilding TTL files from tmp/dim_*.csv ...")
    result = subprocess.run(
        [sys.executable, str(HERE / "build_graphdb_ttl.py")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [ERROR] build_graphdb_ttl.py failed:\n{result.stderr}")
        sys.exit(1)
    for line in result.stdout.strip().splitlines():
        print(f"  {line}")
    print(f"  DDL : {DDL_FILE.stat().st_size:,} bytes")
    print(f"  DML : {DML_FILE.stat().st_size:,} bytes")

    # Step 2 — Check GraphDB reachable
    print("\n[2] Checking GraphDB at localhost:7200...")
    try:
        _get(f"{GRAPHDB_BASE}/rest/repositories")
        print("  Reachable.")
    except Exception as e:
        print(f"  [ERROR] Cannot reach GraphDB: {e}")
        print("  Start GraphDB first, then re-run.")
        sys.exit(1)

    # Step 3 — Create repo if missing
    print(f"\n[3] Ensuring repository '{REPO_ID}' exists...")
    _ensure_repo()

    # Step 4 — Clear existing data
    print("\n[4] Clearing existing triples...")
    _clear_repo()

    # Step 5 — Load DDL
    print(f"\n[5] Loading DDL (schema)...")
    _post_ttl(DDL_FILE)

    # Step 6 — Load DML
    print(f"\n[6] Loading DML (instance data — may take 30s)...")
    _post_ttl(DML_FILE)

    # Step 7 — Verify
    print("\n[7] Verifying triple count...")
    try:
        n = _triple_count()
        print(f"  {n:,} triples loaded into '{REPO_ID}'")
        if n < 10000:
            print("  [WARNING] Unexpectedly low — expected ~54k triples. Check GraphDB logs.")
        else:
            print("  Ready. Run pipeline.py.")
    except Exception as e:
        print(f"  [WARNING] Could not verify: {e}")
        print("  Data was likely loaded — check http://localhost:7200")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
