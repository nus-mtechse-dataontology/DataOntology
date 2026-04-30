"""PostgreSQL database — connects to the shared fact_flight_info table via the production DAO stack."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

# Make src/ importable when running directly from src/graphdb/
_src_root = str(Path(__file__).resolve().parent.parent)
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

# Point PostgresDriver at the project root for vault file resolution
_project_root = str(Path(__file__).resolve().parents[2])
os.environ.setdefault("PROJECT_PATH", _project_root)

from dao.fact_flight_info_dao import FactFlightInfoDAO  # noqa: E402
from session.db_session import DBSession  # noqa: E402

_dao: FactFlightInfoDAO | None = None


def _load_config() -> dict:
    config_path = Path(_project_root) / "resources" / "config.toml"
    with open(config_path) as f:
        return tomllib.loads(f.read())


def _get_dao() -> FactFlightInfoDAO:
    global _dao
    if _dao is None:
        config = _load_config()
        session = DBSession(config)
        _dao = FactFlightInfoDAO(session.engine)
        print("  [db] Connected to PostgreSQL (fact_flight_info)")
    return _dao


def execute_sql(sql: str, params: dict) -> list[dict]:
    dao = _get_dao()
    rows = dao.execute_raw_query(sql, params)
    return [dict(r) for r in rows]
