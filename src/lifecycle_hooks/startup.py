"""Application startup: wire all pipeline components into the Orchestrator."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import tomllib
import traceback

from fastapi import FastAPI
from sqlmodel import SQLModel

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
from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.providers.gemini_gateway import GeminiGateway
from llm_gateway.providers.openai_gateway import OpenAIGateway
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from prompt_builder.prompt_builder import PromptBuilder
from validators.semantic.semantic_validator import SemanticValidator
from validators.syntactic.syntactic_validator import SyntacticValidator

logger = logging.getLogger("data_ontology")


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
    # ── Register LLM Providers ──────────────────────────────────────
    GatewayRegistry.register("gemini", GeminiGateway)
    GatewayRegistry.register("openai", OpenAIGateway)
    logger.info("Registered LLM providers: %s", ", ".join(GatewayRegistry.get_all().keys()))
    
    # ── Configuration ────────────────────────────────────────────────
    config = load_config()
    llm_config = config.get("llm", {})
    
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
    
    # ── Create components ────────────────────────────────────────────
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
    
    app.state.orchestrator = orchestrator
    app.state.session = session
    app.state.auth = AuthenticationService(account_dao, jwt_handler)
    app.state.jwt_handler = jwt_handler
    app.state.registration = RegistrationService(registration_dao, account_dao)
    
    yield
