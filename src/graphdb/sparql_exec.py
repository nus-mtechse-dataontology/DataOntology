"""
Execute SPARQL queries against the local GraphDB instance.

Supports:
  - SELECT  → list[dict]   (application/sparql-results+json)
  - CONSTRUCT → rdflib.Graph  (text/turtle)

Uses only urllib (no third-party HTTP client needed).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from rdflib import Graph

from graphdb.config import GRAPHDB_TIMEOUT


GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200/repositories/dataontology")


def _post(sparql: str, accept: str) -> bytes:
    data = urllib.parse.urlencode({"query": sparql}).encode()
    req = urllib.request.Request(
        GRAPHDB_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": accept,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=GRAPHDB_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        raise ConnectionError(
            f"GraphDB HTTP {e.code} from {GRAPHDB_URL}.\nResponse: {body}"
        )
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"GraphDB unreachable at {GRAPHDB_URL}. Is it running?\nDetails: {e}"
        )


def execute_select(sparql: str) -> list[dict]:
    """Fire a SELECT query, return list of row dicts keyed by variable name."""
    raw = _post(sparql, "application/sparql-results+json")
    result = json.loads(raw)
    vars_ = result["results"]["bindings"] and result["head"]["vars"]
    rows = []
    for binding in result["results"]["bindings"]:
        row = {}
        for var in result["head"]["vars"]:
            cell = binding.get(var)
            row[var] = cell["value"] if cell else None
        rows.append(row)
    return rows


def execute_construct(sparql: str) -> Graph:
    """Fire a CONSTRUCT query, parse the Turtle response into an rdflib Graph."""
    raw = _post(sparql, "text/turtle")
    g = Graph()
    g.parse(data=raw.decode(), format="turtle")
    return g


def check_graphdb() -> bool:
    """Ping GraphDB — return True if reachable and repository exists."""
    # Use the repository size endpoint — returns 200 + triple count as plain text
    size_url = GRAPHDB_URL.rstrip("/") + "/size"
    try:
        req = urllib.request.Request(size_url, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False
