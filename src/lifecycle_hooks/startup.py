"""Application startup: wire all pipeline components into the Orchestrator."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import tomllib
import traceback

from dotenv import load_dotenv

from fastapi import FastAPI
from sqlmodel import SQLModel

from graphdb.pipeline import GraphDbPipeline

# Ensure the project root is on sys.path so that `graphdb` is importable as a package
# regardless of how the app is launched (python src/main.py, uvicorn, Docker, etc.)
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from graphdb.service import GraphDBService  # noqa: E402
from adapters.telegram import TelegramWebhookHandler, TelegramClient, TelegramUpdateMapper
from dao.fact_flight_info_dao import FactFlightInfoDAO
from handlers import *
from services.auth.jwt_handler import JWTHandler
from ingestion.services.ingestion_service import IngestionService
from dao.ingestion_dao import IngestionDAO
from dao.registration_dao import RegistrationDAO
from services.auth.authentication_service import AuthenticationService
from services.registration.registration_service import RegistrationService
from compiler.sql_compiler import SQLCompiler
from dao.accounts_dao import AccountsDAO
from session.db_session import DBSession
from entities import *
from execution.sql_executor import SQLExecutor
from formatter.telegram_formatter import TelegramFormatter
from formatter.web_formatter import WebFormatter
from llm_gateway.gateway_factory import LLMGatewayFactory
from orchestrator.orchestrator import Orchestrator
from prompt_builder.prompt_builder import PromptBuilder
from validators.semantic.semantic_validator import SemanticValidator
from validators.syntactic.syntactic_validator import SyntacticValidator

logger = logging.getLogger("data_ontology")


def load_env(project_root: Path) -> None:
    if load_dotenv is None:
        logger.warning("python-dotenv is not installed; skipping .env loading.")
        return

    load_dotenv(project_root / ".env", override=False)
    load_dotenv(project_root / "scripts" / "local.env", override=False)


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


def setup_telegram_handler(orchestrator):
    # ── Set Up telegram bot ────────────────────────────────────────────
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        sys.exit("TELEGRAM_BOT_TOKEN is not configured.")
    
    telegram_webhook_handler = TelegramWebhookHandler(
        mapper=TelegramUpdateMapper(),
        orchestrator=orchestrator,
        client=TelegramClient(bot_token)
    )
    
    return telegram_webhook_handler


@asynccontextmanager
async def startup(app: FastAPI):
    """
    Initialise all dependencies for the Application.
    """
    project_root = Path(__file__).resolve().parents[2]
    os.environ.setdefault("PROJECT_PATH", str(project_root))
    load_env(project_root)

    config = load_config()
    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)
    
    account_dao = AccountsDAO(session.engine)
    registration_dao = RegistrationDAO(session.engine)
    fact_flight_info_dao = FactFlightInfoDAO(session.engine)
    ingestion_dao = IngestionDAO(session.engine)
    
    jwt_handler = JWTHandler(
        secrets.token_urlsafe(32),
        config["jwt"]["expire_mins"],
        config["jwt"]["algo"]
    )
    
    llm_gateway = LLMGatewayFactory.create(config.get("llm", {}))
    prompt_builder = PromptBuilder()
    syntactic_validator = SyntacticValidator()
    semantic_validator = SemanticValidator()
    sql_compiler = SQLCompiler()
    sql_executor = SQLExecutor(fact_flight_info_dao)
    
    formatters: dict[str, type] = {
        "telegram": TelegramFormatter,
        "web": WebFormatter,
    }
    
    # ── Wire GraphDB semantic pipeline ────────────────────────────────
    logger.info("Initialising GraphDBService")
    try:
        graph_db_pipeline = GraphDbPipeline(fact_flight_info_dao)
        graphdb_service = GraphDBService(graph_db_pipeline)
        graphdb_reachable = graphdb_service.graphdb_reachable()
        if graphdb_reachable:
            logger.info(
                "GraphDBService ready — GraphDB reachable at %s",
                os.getenv("GRAPHDB_URL", "http://localhost:7200/repositories/dataontology")
            )
        else:
            logger.warning(
                "GraphDBService ready — GraphDB NOT reachable @ %s; SPARQL intents will fail",
                os.getenv("GRAPHDB_URL", "http://localhost:7200/repositories/dataontology")
            )
    except Exception as e:
        logger.exception("GraphDBService failed to initialise — graphdb queries disabled")
        raise e
    # ──────────────────────────────────────────────────────────────────
    
    graphdb_handler = GraphDBHandler(graphdb_service)
    request_handler = RequestHandler()
    prompt_handler = PromptHandler(prompt_builder)
    llm_handler = LLMHandler(llm_gateway)
    syntactic_validation_handler = SyntacticValidationHandler(syntactic_validator)
    semantics_validation_handler = SemanticsValidationHandler(semantic_validator)
    sql_compiler_handler = SQLCompilerHandler(sql_compiler)
    sql_executor_handler = SQLExecutorHandler(sql_executor)
    response_builder_handler = ResponseFormatterHandler(formatters)
    
    # ── Wire orchestrator ────────────────────────────────────────────
    logger.info("Wiring Orchestrator")
    orchestrator = Orchestrator(
        request_handler,
        prompt_handler,
        llm_handler,
        syntactic_validation_handler,
        semantics_validation_handler,
        sql_compiler_handler,
        sql_executor_handler,
        response_builder_handler,
        graphdb_handler
    )
    logger.info("Orchestrator wired — pipeline ready")
    # ───────────────────────────────────────────────────────────────────
    
    # ── Wire Telegram components ───────────────────────────────────────
    logger.info("Wiring Telegram WebHook")
    configured_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not configured_secret:
        sys.exit("TELEGRAM_WEBHOOK_SECRET is not configured.")
    
    telegram_handler = setup_telegram_handler(orchestrator)
    logger.info("Telegram WebHook wired — Telegram WebHook is ready")
    # ──────────────────────────────────────────────────────────────────────
    
    app.state.orchestrator = orchestrator
    app.state.graphdb_service = graphdb_service
    app.state.session = session
    app.state.auth = AuthenticationService(account_dao, jwt_handler)
    app.state.jwt_handler = jwt_handler
    app.state.telegram_handler = telegram_handler
    app.state.configured_secret = configured_secret
    app.state.registration = RegistrationService(registration_dao, account_dao)
    app.state.ingestion_service = IngestionService(ingestion_dao)
    
    yield
