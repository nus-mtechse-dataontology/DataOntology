"""E2E golden-question regression tests.

Run deliberately with:
    uv run pytest -m e2e

Requires:
    - Local Postgres running with seed data (resources/seed_local.sql)
    - GEMINI_API_KEY set in environment
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
    import secrets
    import tomllib
    from pathlib import Path
    from datetime import datetime, timezone

    from compiler.sql_compiler import SQLCompiler
    from dao.fact_flight_info_dao import FactFlightInfoDAO
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
    from session.db_session import DBSession
    from validators.semantic.semantic_validator import SemanticValidator
    from validators.syntactic.syntactic_validator import SyntacticValidator
    from sqlmodel import SQLModel

    config_path = Path(os.getenv("PROJECT_PATH", os.getcwd())) / "resources" / "config.toml"
    with open(config_path) as f:
        config = tomllib.loads(f.read())

    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)

    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    semantic_model_path = os.getenv(
        "SEMANTIC_MODEL_PATH",
        str(src_dir / "ontology" / "semantic_layer_v2.json"),
    )

    GatewayRegistry.register("gemini", GeminiGateway)
    GatewayRegistry.register("openai", OpenAIGateway)

    llm_config = config.get("llm", {})
    provider = os.getenv("LLM_PROVIDER") or llm_config.get("provider", "gemini")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("LLM_MODEL") or llm_config.get("providers", {}).get(provider, {}).get("model")
    timeout = int(os.getenv("LLM_TIMEOUT", "30"))

    llm_gateway = LLMGatewayFactory.create(provider=provider, api_key=api_key, model=model, timeout_seconds=timeout)

    loader = SemanticModelLoader()
    semantic_model = loader.load(semantic_model_path)

    fact_flight_info_dao = FactFlightInfoDAO(session.engine)

    return Orchestrator(
        semantic_model_provider=lambda: SuccessResponse(request_id="system", data=semantic_model),
        prompt_builder=PromptBuilder().build,
        llm_gateway=llm_gateway.submit_prompt,
        syntactic_validator=SyntacticValidator().validate,
        semantic_validator=SemanticValidator().validate,
        sql_compiler=SQLCompiler().compile,
        sql_executor=SQLExecutor(fact_flight_info_dao).execute,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.e2e
@pytest.mark.external
@pytest.mark.parametrize("case", GOLDEN_QUESTIONS, ids=[c["id"] for c in GOLDEN_QUESTIONS])
def test_golden_question(orchestrator, case):
    from models.pipeline import NLQRequest
    from models.common import SuccessResponse
    import uuid

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
