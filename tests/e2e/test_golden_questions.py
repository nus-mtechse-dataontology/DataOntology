"""E2E golden-question regression tests.

Run deliberately with:
    uv run pytest -m e2e

Requires:
    - Local Postgres running with seed data (resources/seed_local.sql)
    - GEMINI_API_KEY (or LLM_API_KEY + LLM_PROVIDER) set in environment
    - PROJECT_PATH set to repo root
    - Server NOT required — tests call the orchestrator directly
"""

import os

import pytest

GOLDEN_QUESTIONS = [
    {
        "id": "cheapest_flight_on_route",
        "question": "What is the cheapest flight from SIN to BKK between 1 June and 30 June 2025?",
        "expect_success": True,
        "expected_record_count": 6,
        "expected_contains": ["SIN", "BKK", "89"],
    },
    {
        "id": "destinations_under_budget",
        "question": "Where can I fly from SIN for under 300 SGD between 1 June and 30 June 2025?",
        "expect_success": True,
        "expected_record_count": 3,
        "expected_contains": ["KUL", "BKK", "CNX"],
    },
    {
        "id": "destinations_by_country",
        "question": "From SIN, which airports in Thailand can I fly to in June 2025?",
        "expect_success": True,
        "expected_record_count": 2,
        "expected_contains": ["BKK", "CNX", "Thailand"],
    },
    {
        "id": "route_fare_options",
        "question": "Show me all fare options from SIN to BKK between 1 June and 30 June 2025",
        "expect_success": True,
        "expected_record_count": 6,
        "expected_contains": ["AirAsia", "Economy"],
    },
    {
        "id": "airlines_on_route",
        "question": "Which airlines fly from SIN to BKK in June 2025?",
        "expect_success": True,
        "expected_record_count": 4,
        "expected_contains": ["AirAsia", "Singapore Airlines"],
    },
    {
        "id": "last_seat_urgency",
        "question": "Are there any almost-full flights from SIN to BKK in June 2025?",
        "expect_success": True,
        "expected_record_count": 5,
        "expected_contains": ["AirAsia", "Economy"],
    },
]


@pytest.fixture(scope="module")
def orchestrator():
    """Wire up a real orchestrator using env vars and local Postgres."""
    import tomllib
    from pathlib import Path

    from sqlmodel import SQLModel

    from compiler.sql_compiler import SQLCompiler
    from dao.fact_flight_info_dao import FactFlightInfoDAO
    from execution.sql_executor import SQLExecutor
    from handlers import (
        LLMHandler,
        PromptHandler,
        RequestHandler,
        ResponseBuilderHandler,
        SemanticsValidationHandler,
        SQLCompilerHandler,
        SQLExecutorHandler,
        SyntacticValidationHandler,
    )
    from llm_gateway.gateway_factory import LLMGatewayFactory
    from llm_gateway.gateway_registry import GatewayRegistry
    from llm_gateway.providers.gemini_gateway import GeminiGateway
    from llm_gateway.providers.openai_gateway import OpenAIGateway
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.response_builder import ResponseBuilder
    from prompt_builder.prompt_builder import PromptBuilder
    from session.db_session import DBSession
    from validators.semantic.semantic_validator import SemanticValidator
    from validators.syntactic.syntactic_validator import SyntacticValidator

    project_path = os.getenv("PROJECT_PATH", os.getcwd())
    config_path = Path(project_path) / "resources" / "config.toml"
    with open(config_path) as f:
        config = tomllib.loads(f.read())

    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)

    GatewayRegistry.register("gemini", GeminiGateway)
    GatewayRegistry.register("openai", OpenAIGateway)

    llm_config = config.get("llm", {})
    provider = os.getenv("LLM_PROVIDER") or llm_config.get("provider", "gemini")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("LLM_MODEL") or llm_config.get("providers", {}).get(provider, {}).get("model")
    timeout = int(os.getenv("LLM_TIMEOUT", str(llm_config.get("providers", {}).get(provider, {}).get("timeout_seconds", 30))))

    llm_gateway = LLMGatewayFactory.create(
        provider=provider,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
    )

    fact_flight_info_dao = FactFlightInfoDAO(session.engine)

    return Orchestrator(
        request_handler=RequestHandler(),
        prompt_handler=PromptHandler(PromptBuilder()),
        llm_handler=LLMHandler(llm_gateway),
        syntactic_validation_handler=SyntacticValidationHandler(SyntacticValidator()),
        semantics_validation_handler=SemanticsValidationHandler(SemanticValidator()),
        sql_compiler_handler=SQLCompilerHandler(SQLCompiler()),
        sql_executor_handler=SQLExecutorHandler(SQLExecutor(fact_flight_info_dao)),
        response_builder_handler=ResponseBuilderHandler(ResponseBuilder()),
    )


@pytest.mark.e2e
@pytest.mark.external
@pytest.mark.parametrize("case", GOLDEN_QUESTIONS, ids=[c["id"] for c in GOLDEN_QUESTIONS])
def test_golden_question(orchestrator, case):
    import uuid

    from models.common import SuccessResponse
    from models.pipeline import NLQRequest

    request = NLQRequest(request_id=str(uuid.uuid4()), question=case["question"])
    result = orchestrator.handle_question(request)

    if case["expect_success"]:
        assert isinstance(result, SuccessResponse), (
            f"Expected success but got error: {result.error.message if hasattr(result, 'error') else result}"
        )
        response = result.data.response
        expected_count = case["expected_record_count"]
        assert f"I found {expected_count} matching" in response, (
            f"Expected {expected_count} records in response: {response}"
        )
        for substring in case["expected_contains"]:
            assert substring in response, (
                f"Expected '{substring}' in response: {response}"
            )
    else:
        assert not isinstance(result, SuccessResponse)
