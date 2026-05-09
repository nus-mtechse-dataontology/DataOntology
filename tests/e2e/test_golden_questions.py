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
from sqlalchemy import text

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
        "expected_contains": [],
    },
    {
        "id": "destinations_by_country",
        "question": "From SIN, which airports in Thailand can I fly to in June 2025?",
        "expect_success": True,
        "expected_record_count": 2,
        "expected_contains": [],
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

    # project_path = os.getenv("PROJECT_PATH", os.getcwd())
    
    config = {
        'datasource': {
            'driver': {
                'package': 'drivers.sqlite_driver',
                'class': 'SQLiteDriver',
                'options': {}
            },
            'database': {
                'connection_url': 'sqlite:///:memory:',
                'options': {
                    'echo': False
                }
            }
        }
    }
    
    seed_sql = """
               INSERT INTO dim_country (f_country_code, f_country_name) \
               VALUES ('SG', 'Singapore'), \
                      ('TH', 'Thailand'), \
                      ('MY', 'Malaysia'), \
                      ('JP', 'Japan') ON CONFLICT (f_country_code) DO NOTHING;
               
               INSERT INTO dim_city (f_city_code, f_city_name, f_country_code) \
               VALUES ('SIN', 'Singapore', 'SG'), \
                      ('BKK', 'Bangkok', 'TH'), \
                      ('CNX', 'Chiang Mai', 'TH'), \
                      ('KUL', 'Kuala Lumpur', 'MY'), \
                      ('NRT', 'Tokyo', 'JP') ON CONFLICT (f_city_code) DO NOTHING;
               
               INSERT INTO dim_airport (f_airport_code, f_airport_name, f_city_code) \
               VALUES ('SIN', 'Singapore Changi Airport', 'SIN'), \
                      ('BKK', 'Suvarnabhumi Airport', 'BKK'), \
                      ('CNX', 'Chiang Mai International Airport', 'CNX'), \
                      ('KUL', 'Kuala Lumpur International', 'KUL'), \
                      ('NRT', 'Narita International Airport', 'NRT') ON CONFLICT (f_airport_code) DO NOTHING;
               
               INSERT INTO dim_airline (f_airline_code, f_airline_name) \
               VALUES ('SQ', 'Singapore Airlines'), \
                      ('TG', 'Thai Airways'), \
                      ('AK', 'AirAsia'), \
                      ('MH', 'Malaysia Airlines') ON CONFLICT (f_airline_code) DO NOTHING;
               
               INSERT INTO dim_aircraft (f_aircraft_code, f_aircraft_model) \
               VALUES ('773', 'Boeing 777-300'), \
                      ('320', 'Airbus A320'), \
                      ('333', 'Airbus A330-300') ON CONFLICT (f_aircraft_code) DO NOTHING;
               
               INSERT INTO dim_currency_rate (f_currency_code, f_currency_name, f_currency_rate) \
               VALUES ('SGD', 'Singapore Dollar', 1.00), \
                      ('THB', 'Thai Baht', 0.037) ON CONFLICT (f_currency_code) DO NOTHING;
               
               INSERT INTO fact_flight_info (f_flight_combination, f_departure_airport_code, f_destination_airport_code, \
                                             f_airline_code, f_currency_code, f_aircraft_code, \
                                             f_departure_date, f_arrival_date, \
                                             f_cabin_class, f_trip_type, \
                                             f_num_of_last_seats, f_flight_duration, f_total_amount_fare_total) \
               VALUES (1001, 'SIN', 'BKK', 'AK', 'SGD', '320', '2025-06-05 08:00', '2025-06-05 11:30', 'Economy', 'OW', \
                       12, 210, 89.00), \
                      (1002, 'SIN', 'BKK', 'TG', 'SGD', '333', '2025-06-05 14:00', '2025-06-05 17:30', 'Economy', 'OW', \
                       3, 210, 145.00), \
                      (1003, 'SIN', 'BKK', 'SQ', 'SGD', '773', '2025-06-05 10:00', '2025-06-05 13:30', 'Business', 'OW', \
                       2, 210, 520.00), \
                      (1004, 'SIN', 'BKK', 'AK', 'SGD', '320', '2025-06-10 09:00', '2025-06-10 12:30', 'Economy', 'OW', \
                       1, 210, 95.00), \
                      (1005, 'SIN', 'BKK', 'MH', 'SGD', '320', '2025-06-08 07:00', '2025-06-08 10:30', 'Economy', 'OW', \
                       5, 210, 118.00), \
                      (1006, 'SIN', 'BKK', 'TG', 'SGD', '333', '2025-06-12 16:00', '2025-06-12 19:30', 'Business', 'OW', \
                       1, 210, 480.00), \
                      (2001, 'SIN', 'CNX', 'AK', 'SGD', '320', '2025-06-07 07:00', '2025-06-07 11:30', 'Economy', 'OW', \
                       20, 270, 112.00), \
                      (2002, 'SIN', 'CNX', 'TG', 'SGD', '333', '2025-06-15 13:00', '2025-06-15 17:30', 'Economy', 'OW', \
                       8, 270, 178.00), \
                      (3001, 'SIN', 'KUL', 'AK', 'SGD', '320', '2025-06-03 06:00', '2025-06-03 07:30', 'Economy', 'OW', \
                       30, 90, 55.00), \
                      (3002, 'SIN', 'KUL', 'MH', 'SGD', '320', '2025-06-03 12:00', '2025-06-03 13:30', 'Economy', 'OW', \
                       15, 90, 72.00), \
                      (4001, 'SIN', 'NRT', 'SQ', 'SGD', '773', '2025-06-05 09:00', '2025-06-05 17:00', 'Economy', 'OW', \
                       10, 480, 450.00), \
                      (4002, 'SIN', 'NRT', 'SQ', 'SGD', '773', '2025-06-05 09:00', '2025-06-05 17:00', 'Business', 'OW', \
                       4, 480, 1200.00) ON CONFLICT (f_flight_combination) DO NOTHING; \
               """
    
    # Split by semicolon, filter out empty strings and comments
    statements = [
        stmt.strip()
        for stmt in seed_sql.split(";")
        if stmt.strip() and not stmt.strip().startswith("--")
    ]
    
    session = DBSession(config)
    SQLModel.metadata.create_all(session.engine)
    with session.engine.begin() as connection:
        for stmt in statements:
            # Remove any leading comments within the statement
            cleaned = "\n".join(
                line for line in stmt.split("\n")
                if not line.strip().startswith("--")
            ).strip()
            if cleaned:
                connection.execute(text(cleaned))

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
