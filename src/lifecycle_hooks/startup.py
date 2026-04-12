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

from adapters.telegram import TelegramWebhookHandler, TelegramClient, TelegramFormatter, TelegramUpdateMapper
from dao.fact_flight_info_dao import FactFlightInfoDAO
from handlers import *
from services.auth.jwt_handler import JWTHandler
from dao.registration_dao import RegistrationDAO
from services.auth.authentication_service import AuthenticationService
from services.registration.registration_service import RegistrationService
from compiler.sql_compiler import SQLCompiler
from dao.accounts_dao import AccountsDAO
from session.db_session import DBSession
from entities import *
from execution.sql_executor import SQLExecutor
from llm_gateway.gateway_factory import LLMGatewayFactory
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
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


def init_llm_gateway():
    config = load_config()
    llm_config = config.get("llm", {})
    providers_config = llm_config.get("providers", {})
    llm_provider = (llm_config.get("provider") or "gemini").lower()
    selected_provider_config = providers_config.get(llm_provider, {})

    llm_api_key = selected_provider_config.get("api_key")
    llm_model = selected_provider_config.get("model")
    llm_timeout_raw = str(
        selected_provider_config.get(
            "timeout_seconds",
            llm_config.get("timeout_seconds", 30),
        )
    )

    try:
        llm_timeout_seconds = int(llm_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid LLM timeout value: {llm_timeout_raw}") from exc

    try:
        llm_gateway = LLMGatewayFactory.create(
            provider=llm_provider,
            api_key=llm_api_key,
            model=llm_model,
            timeout_seconds=llm_timeout_seconds,
        )
        logger.info(
            "Created LLM gateway: provider=%s, model=%s, timeout_seconds=%s",
            llm_provider,
            llm_model or "default",
            llm_timeout_seconds,
        )
        
        return llm_gateway
    
    except ValueError as e:
        logger.error("Failed to create LLM gateway: %s", e)
        raise


def setup_telegram_handler(orchestrator):
    # ── Set Up telegram bot ────────────────────────────────────────────
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        sys.exit("TELEGRAM_BOT_TOKEN is not configured.")
    
    telegram_webhook_handler = TelegramWebhookHandler(
        mapper=TelegramUpdateMapper(),
        orchestrator=orchestrator,
        client=TelegramClient(bot_token),
        formatter=TelegramFormatter()
    )
    
    return telegram_webhook_handler


@asynccontextmanager
async def startup(app: FastAPI):
    """
    Initialise all dependencies for the Application.

    config.toml LLM section:
        [llm]
        provider = "gemini"
        timeout_seconds = 30

        [llm.providers.gemini]
        model = "gemini-3-flash-preview"
        # timeout_seconds = 30
        # api_key = "..."

        [llm.providers.openai]
        model = "gpt-5-nano"
        # timeout_seconds = 30
        # api_key = "..."

    Provider resolution order:
        1) config.toml [llm].provider
        2) default 'gemini'
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
    
    jwt_handler = JWTHandler(
        secrets.token_urlsafe(32),
        config["jwt"]["expire_mins"],
        config["jwt"]["algo"]
    )
    
    llm_gateway = init_llm_gateway()
    prompt_builder = PromptBuilder()
    syntactic_validator = SyntacticValidator()
    semantic_validator = SemanticValidator()
    sql_compiler = SQLCompiler()
    sql_executor = SQLExecutor(fact_flight_info_dao)
    response_builder = ResponseBuilder()
    
    request_handler = RequestHandler()
    prompt_handler = PromptHandler(prompt_builder)
    llm_handler = LLMHandler(llm_gateway)
    syntactic_validation_handler = SyntacticValidationHandler(syntactic_validator)
    semantics_validation_handler = SemanticsValidationHandler(semantic_validator)
    sql_compiler_handler = SQLCompilerHandler(sql_compiler)
    sql_executor_handler = SQLExecutorHandler(sql_executor)
    response_builder_handler = ResponseBuilderHandler(response_builder)
    
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
        response_builder_handler
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
    app.state.session = session
    app.state.auth = AuthenticationService(account_dao, jwt_handler)
    app.state.jwt_handler = jwt_handler
    app.state.telegram_handler = telegram_handler
    app.state.configured_secret = configured_secret
    app.state.registration = RegistrationService(registration_dao, account_dao)
    
    yield
