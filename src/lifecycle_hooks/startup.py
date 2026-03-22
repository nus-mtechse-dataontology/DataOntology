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
from llm_gateway.gateway_factory import LLMGatewayFactory
from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.providers.gemini_gateway import GeminiGateway
from llm_gateway.providers.openai_gateway import OpenAIGateway
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
        LLM_PROVIDER     - Optional override for configured LLM provider ('gemini' or 'openai')
        LLM_API_KEY      - Optional override API key for the selected LLM provider
        LLM_MODEL        - Optional override model name for the selected LLM provider
        LLM_TIMEOUT      - Optional override timeout in seconds for the selected provider
        GEMINI_API_KEY   - (Deprecated) API key for Gemini LLM (use LLM_API_KEY with LLM_PROVIDER=gemini)
        GEMINI_MODEL     - (Deprecated) Gemini model fallback when LLM_MODEL/config model is absent
        OPENAI_API_KEY   - (Alternative) OpenAI API key (use LLM_API_KEY with LLM_PROVIDER=openai)
        OPENAI_MODEL     - (Alternative) OpenAI model fallback when LLM_MODEL/config model is absent
        DB_PATH          - Path to SQLite database (default: resources/flights.db)
        SEMANTIC_MODEL_PATH - Path to semantic_layer.json (default: auto-detected)

    config.toml LLM section:
        [llm]
        provider = "gemini"

        [llm.providers.gemini]
        model = "gemini-3-flash-preview"
        timeout_seconds = 30

        [llm.providers.openai]
        model = "gpt-5.4-nano"
        timeout_seconds = 30

    Provider resolution order:
        1) LLM_PROVIDER environment override
        2) config.toml [llm].provider
        3) If still unset and exactly one provider key exists, infer that provider
        4) If still unset and multiple provider keys exist, startup fails and requires explicit provider
        5) If still unset and no provider keys exist, defaults to gemini (backward compatibility)

    If provider is inferred from API keys (no explicit provider from env/config):
        1) If exactly one provider key exists, infer that provider.
        2) If multiple provider keys exist, startup fails and requires LLM_PROVIDER.
        3) If no provider keys exist, defaults to gemini (backward compatibility).
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

    # ── Register LLM Providers ──────────────────────────────────────
    GatewayRegistry.register("gemini", GeminiGateway)
    GatewayRegistry.register("openai", OpenAIGateway)
    logger.info("Registered LLM providers: %s", ", ".join(GatewayRegistry.get_all().keys()))

    # ── Configuration ────────────────────────────────────────────────
    config = load_config()
    llm_config = config.get("llm", {})

    db_path = os.getenv("DB_PATH", _DEFAULT_DB_PATH)
    semantic_model_path = os.getenv("SEMANTIC_MODEL_PATH", _DEFAULT_SEMANTIC_MODEL_PATH)
    
    # LLM provider selection policy:
    # 1) Respect explicit LLM_PROVIDER if set.
    # 2) If not set and exactly one provider key exists, infer that provider.
    # 3) If not set and multiple provider keys exist, fail fast and require LLM_PROVIDER.
    # 4) If not set and no provider keys exist, default to gemini for backward compatibility.
    config_provider = llm_config.get("provider")
    providers_config = llm_config.get("providers", {})

    explicit_provider = os.getenv("LLM_PROVIDER") or config_provider
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    openai_model = os.getenv("OPENAI_MODEL")

    if explicit_provider:
        llm_provider = explicit_provider
    else:
        detected_providers: list[str] = []
        if gemini_api_key:
            detected_providers.append("gemini")
        if openai_api_key:
            detected_providers.append("openai")

        if len(detected_providers) == 1:
            llm_provider = detected_providers[0]
            logger.info("Inferred LLM provider from configured API key: %s", llm_provider)
        elif len(detected_providers) > 1:
            raise ValueError(
                "Multiple LLM API keys detected but LLM_PROVIDER is not set. "
                "Set LLM_PROVIDER explicitly (e.g., 'gemini' or 'openai')."
            )
        else:
            llm_provider = "gemini"
            logger.warning(
                "No provider-specific API key detected and LLM_PROVIDER not set. "
                "Defaulting to provider=gemini."
            )

    llm_api_key = os.getenv("LLM_API_KEY")
    if not llm_api_key:
        if llm_provider == "gemini":
            llm_api_key = gemini_api_key
        elif llm_provider == "openai":
            llm_api_key = openai_api_key

    selected_provider_config = providers_config.get(llm_provider, {})
    config_model = selected_provider_config.get("model")
    config_timeout = selected_provider_config.get("timeout_seconds", 30)

    llm_model = os.getenv("LLM_MODEL") or config_model
    if not llm_model:
        if llm_provider == "gemini":
            llm_model = gemini_model
        elif llm_provider == "openai":
            llm_model = openai_model

    llm_timeout_raw = os.getenv("LLM_TIMEOUT")
    if llm_timeout_raw is None:
        llm_timeout_raw = str(config_timeout)

    try:
        llm_timeout_seconds = int(llm_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid LLM timeout value: {llm_timeout_raw}") from exc

    # ── Load semantic model ──────────────────────────────────────────
    loader = SemanticModelLoader()
    semantic_model = loader.load(semantic_model_path)
    logger.info("Loaded semantic model from %s (%d intents)",
                semantic_model_path, len(semantic_model.get("intents", {})))

    def semantic_model_provider():
        return SuccessResponse(request_id="system", data=semantic_model)

    # ── Create components ────────────────────────────────────────────
    prompt_builder = PromptBuilder()
    
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
    except ValueError as e:
        logger.error("Failed to create LLM gateway: %s", e)
        raise
    
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
    if not llm_api_key:
        logger.warning("LLM API key not set — LLM calls will fail (set %s_API_KEY or LLM_API_KEY)", llm_provider.upper())
    if not Path(db_path).exists():
        logger.warning("Database not found at %s — SQL execution will fail", db_path)
    
    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)
    
    account_dao = AccountsDAO(session.engine)
    registration_dao = RegistrationDAO(session.engine)
    jwt_handler = JWTHandler(
        secrets.token_urlsafe(32),
        config["jwt"]["expire_mins"],
        config["jwt"]["algo"]
    )
    
    app.state.orchestrator = orchestrator
    app.state.session = session
    app.state.auth = AuthenticationService(account_dao, jwt_handler)
    app.state.jwt_handler = jwt_handler
    app.state.registration = RegistrationService(registration_dao, account_dao)
    
    yield
