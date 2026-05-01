"""GraphDB pipeline service — importable by the FastAPI app."""
import io
import logging
import re
import sys
import threading
from pathlib import Path

# Ensure graphdb's own bare-import modules are resolvable when this package
# is imported from outside the graphdb/ directory.
_GRAPHDB_DIR = str(Path(__file__).parent)
if _GRAPHDB_DIR not in sys.path:
    sys.path.insert(0, _GRAPHDB_DIR)

from loader import build_prompt_context, load_semantics  # noqa: E402
from graphdb.pipeline import GraphDbPipeline          # noqa: E402
from sparql_exec import check_graphdb  # noqa: E402

logger = logging.getLogger(__name__)

# Lines that are pipeline-internal progress markers, not user-facing content.
_DEBUG_RE = re.compile(
    r"^─+$"
    r"|^\[Phase \d+\]"
    r"|^\s+\[(?:llm|sparql|sql|db|transit|enrich|visa|enrichment)\]"
    r"|^\s+(?:Intent|Confidence|Params|execution_phase|sparql_type"
    r"|missing_params|follow_up_question)\s*:"
)

# Serialise graphdb calls — run_once() touches global state (SQLite connection,
# sys.stdout redirect) so concurrent calls must be queued.
_lock = threading.Lock()


def _strip_debug(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not _DEBUG_RE.match(ln)]
    return "\n".join(lines).strip()


class GraphDBService:
    def __init__(self, graphdb_pipline: GraphDbPipeline) -> None:
        self._semantics = load_semantics()
        self._intents_str, self._param_schema_str = build_prompt_context(self._semantics)
        self._graphdb_pipeline = graphdb_pipline
        logger.info(
            "GraphDBService ready — %d intents loaded",
            len(self._semantics["intents"]),
        )

    def graphdb_reachable(self) -> bool:
        """Return True if the GraphDB SPARQL endpoint is reachable."""
        return check_graphdb()

    def ask(self, question: str, history: list | None = None) -> str | None:
        """
        Run a question through the graphdb pipeline.

        Returns a formatted response string on success, or None when the
        pipeline cannot handle the question (caller should fall back to the
        existing orchestrator chain).
        """
        with _lock:
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                plan = self._graphdb_pipeline.run_once(
                    question,
                    self._semantics,
                    self._intents_str,
                    self._param_schema_str,
                    history=history,
                )
            except Exception:
                logger.exception("GraphDBService.ask raised an exception")
                plan = None
            finally:
                sys.stdout = old_stdout

        result = _strip_debug(buf.getvalue())

        if plan is None:
            # LLM failure, unknown intent, or missing required params —
            # signal the caller to fall through to the orchestrator.
            return None

        return result or None
