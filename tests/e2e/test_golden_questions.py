"""E2E golden-question regression tests.

Run deliberately with:
    uv run pytest -m e2e

Requires:
    - Local Postgres running with seed data (resources/seed_local.sql)
    - GEMINI_API_KEY (or LLM_API_KEY + LLM_PROVIDER) set in environment
    - PROJECT_PATH set to repo root
    - Server NOT required — tests call the orchestrator directly
"""

import json
import os

import pytest

from formatter.telegram_formatter import TelegramFormatter
from formatter.web_formatter import WebFormatter
from models.pipeline import LLMRawResponse, NLQRequest


class GoldenQuestionGateway:
    def submit_prompt(self, bundle: NLQRequest) -> LLMRawResponse:
        question = next(
            line.removeprefix("Question: ").strip()
            for line in bundle.user_message.splitlines()
            if line.startswith("Question: ")
        )
        base_params = {
            "origin": "SIN",
            "start_date": "2025-06-01",
            "end_date": "2025-06-30",
        }

        if "under 300" in question:
            intent = "destinations_under_budget"
            params = {**base_params, "max_price": 300}
        elif "airports in Thailand" in question:
            intent = "destinations_by_country_from_origin"
            params = {**base_params, "country": "Thailand"}
        elif "all fare options" in question:
            intent = "route_fare_options"
            params = {**base_params, "destination": "BKK"}
        elif "Which airlines fly" in question:
            intent = "airlines_on_route"
            params = {**base_params, "destination": "BKK"}
        elif "almost-full flights" in question:
            intent = "last_seat_urgency"
            params = {**base_params, "destination": "BKK", "max_seats": 5}
        else:
            intent = "cheapest_flight_on_route"
            params = {**base_params, "destination": "BKK"}

        return LLMRawResponse(
            raw_response_text=json.dumps({
                "intent": intent,
                "parameters": params,
                "missing_params": [],
                "follow_up_question": None,
                "confidence": 1.0,
            })
        )


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
        GraphDBHandler,
        LLMHandler,
        PromptHandler,
        RequestHandler,
        ResponseFormatterHandler,
        SemanticsValidationHandler,
        SQLCompilerHandler,
        SQLExecutorHandler,
        SyntacticValidationHandler,
    )
    from graphdb.pipeline import GraphDbPipeline
    from graphdb.service import GraphDBService
    from orchestrator.orchestrator import Orchestrator
    from prompt_builder.prompt_builder import PromptBuilder
    from session.db_session import DBSession
    from validators.semantic.semantic_validator import SemanticValidator
    from validators.syntactic.syntactic_validator import SyntacticValidator
    
    formatters: dict[str, type] = {
        "telegram": TelegramFormatter,
        "web": WebFormatter,
    }

    project_path = os.getenv("PROJECT_PATH", os.getcwd())
    config_path = Path(project_path) / "resources" / "config.toml"
    with open(config_path) as f:
        config = tomllib.loads(f.read())

    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)
    with session.engine.begin() as connection:
        connection.exec_driver_sql("""
            DELETE FROM fact_flight_info
            WHERE f_flight_combination IN (
                1001, 1002, 1003, 1004, 1005, 1006,
                2001, 2002,
                3001, 3002,
                4001, 4002
            )
        """)
        connection.exec_driver_sql((Path(project_path) / "resources" / "seed_local.sql").read_text())

    fact_flight_info_dao = FactFlightInfoDAO(session.engine)
    graphdb_service = GraphDBService(GraphDbPipeline(fact_flight_info_dao))
    graphdb_handler = GraphDBHandler(graphdb_service)

    return Orchestrator(
        request_handler=RequestHandler(),
        prompt_handler=PromptHandler(PromptBuilder()),
        llm_handler=LLMHandler(GoldenQuestionGateway()),
        syntactic_validation_handler=SyntacticValidationHandler(SyntacticValidator()),
        semantics_validation_handler=SemanticsValidationHandler(SemanticValidator()),
        sql_compiler_handler=SQLCompilerHandler(SQLCompiler()),
        sql_executor_handler=SQLExecutorHandler(SQLExecutor(fact_flight_info_dao)),
        response_builder_handler=ResponseFormatterHandler(formatters),
        graphdb_handler=graphdb_handler,
    )


@pytest.mark.e2e
@pytest.mark.external
@pytest.mark.parametrize("case", GOLDEN_QUESTIONS, ids=[c["id"] for c in GOLDEN_QUESTIONS])
def test_golden_question(orchestrator, case):
    import uuid

    from models.common import SuccessResponse
    from models.pipeline import NLQRequest

    request = NLQRequest(
        request_id=str(uuid.uuid4()),
        question=case["question"],
        request_type="flight",
    )
    result = orchestrator.handle_question(request)

    if case["expect_success"]:
        assert isinstance(result, SuccessResponse), (
            f"Expected success but got error: {result.error.message if hasattr(result, 'error') else result}"
        )
        response = "\n".join(result.data)
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
