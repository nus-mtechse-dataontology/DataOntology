"""Full pipeline integration: all real components, only the LLM gateway mocked.

Uses:
    - Real PromptBuilder (with default .j2 template)
    - Real SyntacticValidator
    - Real SemanticValidator
    - Real SQLCompiler
    - Real SQLExecutor (with temp SQLite database seeded with flight data)
    - Real ResponseBuilder + ErrorResponseBuilder
    - Real semantic model loaded from semantic_layer.json
    - Mock LLM gateway (returns canned JSON responses)

This is the closest to end-to-end without making a real LLM call.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

from compiler.sql_compiler import SQLCompiler
from execution.sql_executor import SQLExecutor
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import (
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
)
from ontology.semantic_model_loader import SemanticModelLoader
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from prompt_builder.prompt_builder import PromptBuilder
from validators.semantic.semantic_validator import SemanticValidator
from validators.syntactic.syntactic_validator import SyntacticValidator

import pytest


# ── constants ────────────────────────────────────────────────────────────

REQUEST_ID = "req-full-pipeline-1"
NOW = "2026-02-24T22:00:00Z"

SEMANTIC_MODEL_PATH = str(
    Path(__file__).resolve().parents[3] / "src" / "ontology" / "semantic_layer.json"
)


# ── database setup ───────────────────────────────────────────────────────


def _create_test_db(db_path: str) -> None:
    """Create a SQLite database matching the actual schema used by the
    SQL templates in semantic_layer.json."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        -- Core tables matching the semantic model SQL templates
        CREATE TABLE search_response (
            payload_id  TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            currency_code TEXT NOT NULL,
            trip_type   TEXT NOT NULL
        );

        CREATE TABLE recommendation (
            payload_id              TEXT NOT NULL,
            recommendation_id       TEXT NOT NULL,
            fare_total_amount       REAL NOT NULL,
            fare_amount_without_tax REAL,
            fare_tax                REAL,
            fare_family             TEXT,
            PRIMARY KEY (payload_id, recommendation_id),
            FOREIGN KEY (payload_id) REFERENCES search_response(payload_id)
        );

        CREATE TABLE flight (
            payload_id              TEXT NOT NULL,
            flight_idx              INTEGER NOT NULL,
            origin_airport_code     TEXT NOT NULL,
            destination_airport_code TEXT NOT NULL,
            departure_date          TEXT NOT NULL,
            PRIMARY KEY (payload_id, flight_idx),
            FOREIGN KEY (payload_id) REFERENCES search_response(payload_id)
        );

        CREATE TABLE flight_segment (
            payload_id          TEXT NOT NULL,
            flight_idx          INTEGER NOT NULL,
            segment_idx         INTEGER NOT NULL,
            departure_datetime  TEXT NOT NULL,
            arrival_datetime    TEXT NOT NULL,
            PRIMARY KEY (payload_id, flight_idx, segment_idx),
            FOREIGN KEY (payload_id, flight_idx) REFERENCES flight(payload_id, flight_idx)
        );

        CREATE TABLE flight_leg (
            payload_id    TEXT NOT NULL,
            flight_idx    INTEGER NOT NULL,
            segment_idx   INTEGER NOT NULL,
            leg_idx       INTEGER NOT NULL,
            flight_number TEXT NOT NULL,
            PRIMARY KEY (payload_id, flight_idx, segment_idx, leg_idx),
            FOREIGN KEY (payload_id, flight_idx, segment_idx)
                REFERENCES flight_segment(payload_id, flight_idx, segment_idx)
        );

        CREATE TABLE airport (
            payload_id   TEXT NOT NULL,
            airport_code TEXT NOT NULL,
            city_name    TEXT NOT NULL,
            country_name TEXT NOT NULL,
            PRIMARY KEY (payload_id, airport_code),
            FOREIGN KEY (payload_id) REFERENCES search_response(payload_id)
        );

        -------------------------------------------------------
        -- Seed: SIN→BKK return flight, payload p1 (cheap)
        -------------------------------------------------------
        INSERT INTO search_response VALUES ('p1', 'sess-01', 'SGD', 'R');
        INSERT INTO recommendation   VALUES ('p1', 'rec-01', 180.50, 160.00, 20.50, 'Economy');

        -- Outbound SIN→BKK
        INSERT INTO flight           VALUES ('p1', 0, 'SIN', 'BKK', '2019-09-05');
        INSERT INTO flight_segment   VALUES ('p1', 0, 0, '2019-09-05T08:30:00', '2019-09-05T11:00:00');
        INSERT INTO flight_leg       VALUES ('p1', 0, 0, 0, 'SQ712');
        INSERT INTO airport          VALUES ('p1', 'SIN', 'Singapore', 'Singapore');
        INSERT INTO airport          VALUES ('p1', 'BKK', 'Bangkok', 'Thailand');

        -- Return BKK→SIN
        INSERT INTO flight           VALUES ('p1', 1, 'BKK', 'SIN', '2019-09-12');
        INSERT INTO flight_segment   VALUES ('p1', 1, 0, '2019-09-12T14:00:00', '2019-09-12T18:30:00');
        INSERT INTO flight_leg       VALUES ('p1', 1, 0, 0, 'SQ713');

        -------------------------------------------------------
        -- Seed: SIN→BKK return flight, payload p2 (expensive)
        -------------------------------------------------------
        INSERT INTO search_response VALUES ('p2', 'sess-02', 'SGD', 'R');
        INSERT INTO recommendation   VALUES ('p2', 'rec-02', 320.00, 280.00, 40.00, 'Business');

        INSERT INTO flight           VALUES ('p2', 0, 'SIN', 'BKK', '2019-09-10');
        INSERT INTO flight_segment   VALUES ('p2', 0, 0, '2019-09-10T10:00:00', '2019-09-10T12:30:00');
        INSERT INTO flight_leg       VALUES ('p2', 0, 0, 0, 'TG402');
        INSERT INTO airport          VALUES ('p2', 'SIN', 'Singapore', 'Singapore');
        INSERT INTO airport          VALUES ('p2', 'BKK', 'Bangkok', 'Thailand');

        INSERT INTO flight           VALUES ('p2', 1, 'BKK', 'SIN', '2019-09-17');
        INSERT INTO flight_segment   VALUES ('p2', 1, 0, '2019-09-17T15:00:00', '2019-09-17T19:30:00');
        INSERT INTO flight_leg       VALUES ('p2', 1, 0, 0, 'TG403');

        -------------------------------------------------------
        -- Seed: SIN→NRT return flight, payload p3
        -------------------------------------------------------
        INSERT INTO search_response VALUES ('p3', 'sess-03', 'SGD', 'R');
        INSERT INTO recommendation   VALUES ('p3', 'rec-03', 450.00, 400.00, 50.00, 'Economy');

        INSERT INTO flight           VALUES ('p3', 0, 'SIN', 'NRT', '2019-09-08');
        INSERT INTO flight_segment   VALUES ('p3', 0, 0, '2019-09-08T09:00:00', '2019-09-08T17:00:00');
        INSERT INTO flight_leg       VALUES ('p3', 0, 0, 0, 'SQ638');
        INSERT INTO airport          VALUES ('p3', 'SIN', 'Singapore', 'Singapore');
        INSERT INTO airport          VALUES ('p3', 'NRT', 'Tokyo', 'Japan');

        INSERT INTO flight           VALUES ('p3', 1, 'NRT', 'SIN', '2019-09-15');
        INSERT INTO flight_segment   VALUES ('p3', 1, 0, '2019-09-15T18:00:00', '2019-09-16T00:30:00');
        INSERT INTO flight_leg       VALUES ('p3', 1, 0, 0, 'SQ639');
    """)
    conn.commit()
    conn.close()


def _mock_llm_returning(response_text: str):
    """Create a Mock LLM gateway that returns a canned response."""
    def _gateway(prompt_bundle: PromptBundle):
        return SuccessResponse(
            request_id=prompt_bundle.request_id,
            data=LLMRawResponse(
                request_id=prompt_bundle.request_id,
                raw_response_text=response_text,
            ),
        )
    return _gateway


def _build_full_pipeline(db_path: str, llm_response: str) -> Orchestrator:
    """Build the full orchestrator with all real components except LLM."""
    semantic_model = SemanticModelLoader().load(SEMANTIC_MODEL_PATH)

    return Orchestrator(
        semantic_model_provider=lambda: SuccessResponse(
            request_id=REQUEST_ID, data=semantic_model
        ),
        prompt_builder=PromptBuilder().build,
        llm_gateway=_mock_llm_returning(llm_response),
        syntactic_validator=SyntacticValidator().validate,
        semantic_validator=SemanticValidator().validate,
        sql_compiler=SQLCompiler().compile,
        sql_executor=SQLExecutor(db_path).execute,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: NOW,
    )


# ── tests ────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_cheapest_return_flight_returns_results():
    """End-to-end: user asks for cheapest return flight from SIN to BKK.
    The mock LLM returns a valid QueryPlan, which flows through validation,
    SQL compilation, execution, and response building."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        llm_json = json.dumps({
            "intent": "cheapest_return_flight",
            "parameters": {
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
            },
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.95,
        })

        orchestrator = _build_full_pipeline(db_path, llm_json)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="What is the cheapest return flight from SIN to BKK in September 2019?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert result.request_id == REQUEST_ID
        assert "matching records" in result.data.response
        assert "180.5" in result.data.response  # cheapest fare


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_no_matching_results():
    """LLM returns a valid QueryPlan for a route with no data (SIN to LAX)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        llm_json = json.dumps({
            "intent": "cheapest_return_flight",
            "parameters": {
                "origin": "SIN",
                "destination": "LAX",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
            },
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.90,
        })

        orchestrator = _build_full_pipeline(db_path, llm_json)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="Cheapest flight from SIN to LAX?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "could not find any matching records" in result.data.response


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_malformed_llm_json_returns_syntactic_error():
    """LLM returns garbage → SyntacticValidator catches it → pipeline stops."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        orchestrator = _build_full_pipeline(db_path, "Sorry, I can't help with that.")
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="What is the cheapest flight?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "malformed_json"
        assert result.error.component == "syntactic_validator"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_invalid_intent_returns_semantic_error():
    """LLM returns valid JSON but with unknown intent → SemanticValidator catches it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        llm_json = json.dumps({
            "intent": "book_hotel",
            "parameters": {"city": "Bangkok"},
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.85,
        })

        orchestrator = _build_full_pipeline(db_path, llm_json)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="Book a hotel in Bangkok",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "invalid_intent"
        assert result.error.component == "semantic_validator"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_missing_params_returns_semantic_error():
    """LLM returns valid JSON but missing required params → SemanticValidator catches it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        llm_json = json.dumps({
            "intent": "cheapest_return_flight",
            "parameters": {"origin": "SIN"},  # missing destination, dates
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.70,
        })

        orchestrator = _build_full_pipeline(db_path, llm_json)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="Cheapest flight from Singapore?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "missing_required_params"
        assert result.error.component == "semantic_validator"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_markdown_fenced_llm_response_is_handled():
    """LLM wraps JSON in markdown fences → SyntacticValidator strips them → pipeline succeeds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        raw_json = json.dumps({
            "intent": "cheapest_return_flight",
            "parameters": {
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
            },
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.93,
        })
        llm_text = f"```json\n{raw_json}\n```"

        orchestrator = _build_full_pipeline(db_path, llm_text)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="Cheapest return from SIN to BKK in September?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "matching records" in result.data.response


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_empty_question_returns_prompt_builder_error():
    """Empty question → PromptBuilder rejects → pipeline stops early."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        orchestrator = _build_full_pipeline(db_path, "{}")
        request = NLQRequest(request_id=REQUEST_ID, question="   ")
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.component == "prompt_builder"
        assert result.error.code == "invalid_question"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_full_pipeline_invalid_param_format_returns_semantic_error():
    """LLM returns 'singapore' instead of IATA code 'SIN' → SemanticValidator catches it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "flights.db")
        _create_test_db(db_path)

        llm_json = json.dumps({
            "intent": "cheapest_return_flight",
            "parameters": {
                "origin": "singapore",  # wrong format
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
            },
            "missing_params": [],
            "follow_up_question": None,
            "confidence": 0.80,
        })

        orchestrator = _build_full_pipeline(db_path, llm_json)
        request = NLQRequest(
            request_id=REQUEST_ID,
            question="Cheapest flight from singapore to Bangkok?",
        )
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "invalid_param_format"
        assert result.error.component == "semantic_validator"
