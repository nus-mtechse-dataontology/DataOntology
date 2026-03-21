"""Application startup: wire all pipeline components into the Orchestrator."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import secrets
import tomllib
import traceback

from fastapi import FastAPI
from sqlmodel import SQLModel

from dao.fact_flight_info_dao import FactFlightInfoDAO
from services.auth.jwt_handler import JWTHandler
from dao.registration_dao import RegistrationDAO
from services.auth.authentication_service import AuthenticationService
from services.registration.registration_service import RegistrationService
from compiler.sql_compiler import SQLCompiler
from dao.accounts_dao import AccountsDAO
from session.db_session import DBSession
from entities import *
from execution.sql_executor import SQLExecutor
from llm_gateway.providers.gemini_gateway import GeminiGateway
from models.common import SuccessResponse
from ontology.semantic_model_loader import SemanticModelLoader
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from prompt_builder.prompt_builder import PromptBuilder
from validators.semantic.semantic_validator import SemanticValidator
from validators.syntactic.syntactic_validator import SyntacticValidator

logger = logging.getLogger("data_ontology")

# Default paths (relative to project root)
_SRC_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_SEMANTIC_MODEL_PATH = str(_SRC_DIR / "ontology" / "semantic_layer.json")
_DEFAULT_DB_PATH = str(_SRC_DIR.parent / "resources" / "flights.db")


def load_config() -> dict:
    """
    Loads the config for the named ingestion.
    """
    with open(Path(os.getenv("PROJECT_PATH", os.getcwd()), "resources", "config.toml")) as cf:
        try:
            return tomllib.loads(cf.read())
        
        except tomllib.TOMLDecodeError as exc:
            logger.error("Startup: error while loading config, %s", exc)
            logger.error(traceback.format_exc())
            raise exc
        
def get_key() -> str:
    return secrets.token_urlsafe(32)

@asynccontextmanager
async def startup(app: FastAPI):
    """
    Initialise all dependencies for the Application.

    Environment variables:
        GEMINI_API_KEY   – API key for Gemini LLM (required for LLM calls)
        GEMINI_MODEL     – Gemini model name (default: gemini-3-flash-preview)
        DB_PATH          – Path to SQLite database (default: resources/flights.db)
        SEMANTIC_MODEL_PATH – Path to semantic_layer.json (default: auto-detected)
    """
    
    config = load_config()
    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)
    
    account_dao = AccountsDAO(session.engine)
    registration_dao = RegistrationDAO(session.engine)
    fact_flight_info_dao = FactFlightInfoDAO(session.engine)
    
    jwt_handler = JWTHandler(
        secrets.token_urlsafe(32),
        config["jwt"]["expire_mins"],
        config["jwt"]["algo"]
    )

    # ── Configuration ────────────────────────────────────────────────
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    db_path = os.getenv("DB_PATH", _DEFAULT_DB_PATH)
    semantic_model_path = os.getenv("SEMANTIC_MODEL_PATH", _DEFAULT_SEMANTIC_MODEL_PATH)

    # ── Load semantic model ──────────────────────────────────────────
    loader = SemanticModelLoader()
    semantic_model = loader.load(semantic_model_path)
    logger.info("Loaded semantic model from %s (%d intents)",
                semantic_model_path, len(semantic_model.get("intents", {})))

    def semantic_model_provider():
        return SuccessResponse(request_id="system", data=semantic_model)

    # ── Create components ────────────────────────────────────────────
    prompt_builder = PromptBuilder()
    llm_gateway = GeminiGateway(api_key=gemini_api_key, model=gemini_model)
    syntactic_validator = SyntacticValidator()
    semantic_validator = SemanticValidator()
    sql_compiler = SQLCompiler()
    sql_executor = SQLExecutor(fact_flight_info_dao)
    response_builder = ResponseBuilder()
    error_response_builder = ErrorResponseBuilder()

    # ── Wire orchestrator ────────────────────────────────────────────
    orchestrator = Orchestrator(
        semantic_model_provider=semantic_model_provider,
        prompt_builder=prompt_builder.build,
        llm_gateway=llm_gateway.submit_prompt,
        syntactic_validator=syntactic_validator.validate,
        semantic_validator=semantic_validator.validate,
        sql_compiler=sql_compiler.compile,
        sql_executor=sql_executor.execute,
        response_builder=response_builder.build,
        error_response_builder=error_response_builder.build,
        now_provider=lambda: datetime.now(timezone.utc).isoformat(),
    )
    
    logger.info("Orchestrator wired — pipeline ready (db=%s)", db_path)
    if not gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — LLM calls will fail")
    if not Path(db_path).exists():
        logger.warning("Database not found at %s — SQL execution will fail", db_path)
    
    app.state.orchestrator = orchestrator
    app.state.session = session
    app.state.auth = AuthenticationService(account_dao, jwt_handler)
    app.state.jwt_handler = jwt_handler
    app.state.registration = RegistrationService(registration_dao, account_dao)
    
    yield
