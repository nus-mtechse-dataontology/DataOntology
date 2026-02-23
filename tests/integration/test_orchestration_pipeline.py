"""Integration tests for orchestration pipeline components."""

import json

from llm_gateway.providers.gemini_gateway import GeminiGateway
from models.pipeline import PromptRequest, LLMRawResponse
from prompt_builder.prompt_builder import PromptBuilder


class _FakeResult:
    def __init__(self, output):
        self.output = output


def test_prompt_builder_to_gemini_gateway_with_database(monkeypatch, mock_flight_db):
    """Test full pipeline: PromptBuilder → GeminiGateway → SQL Query → Database."""
    from llm_gateway.providers import gemini_gateway

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            del model_name, system_prompt

        def run_sync(self, user_message):
            del user_message
            return _FakeResult(
                json.dumps({
                    "intent": "cheapest_return_flight",
                    "parameters": {
                        "origin": "SIN",
                        "destination": "BKK",
                        "start_date": "2019-09-01",
                        "end_date": "2019-09-30",
                        "limit": 10
                    },
                    "missing_params": [],
                    "follow_up_question": None,
                    "confidence": 0.92
                })
            )

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)

    template = """Question: {question}
Current time: {current_time}
Semantic model: {semantic_model}

Extract intent and parameters."""

    semantic_model = {
        "intents": {
            "cheapest_return_flight": {
                "description": "Find the lowest-priced return flight between two airports",
                "required_params": ["origin", "destination", "start_date", "end_date"]
            }
        },
        "param_schema": {
            "origin": {"type": "string"},
            "destination": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "limit": {"type": "integer"}
        }
    }

    request = PromptRequest(
        request_id="req-db-001",
        question="What is the cheapest return flight from Singapore to Bangkok?",
        prompt_template=template,
        semantic_model=semantic_model,
    )

    builder = PromptBuilder()
    build_response = builder.build(request)
    assert build_response.status == "SUCCESS"

    gateway = GeminiGateway(api_key="test-key-123")
    llm_response = gateway.submit_prompt(build_response.data)

    assert isinstance(llm_response, LLMRawResponse)
    query_plan = json.loads(llm_response.raw_response_text)
    assert query_plan["intent"] == "cheapest_return_flight"

    sql_query = """
        SELECT sr.session_id, sr.currency_code, MIN(r.fare_total_amount) AS cheapest_return_price,
               MIN(f_out.departure_date) AS outbound_date, MIN(f_in.departure_date) AS return_date
        FROM search_response sr
        JOIN recommendation r ON r.payload_id = sr.payload_id
        JOIN flight f_out ON f_out.payload_id = sr.payload_id
        JOIN flight f_in ON f_in.payload_id = sr.payload_id
        WHERE sr.trip_type = 'R'
        AND f_out.origin_airport_code = :origin
        AND f_out.destination_airport_code = :destination
        AND f_in.origin_airport_code = :destination
        AND f_in.destination_airport_code = :origin
        AND date(f_out.departure_date) BETWEEN date(:start_date) AND date(:end_date)
        GROUP BY sr.session_id, sr.currency_code
        ORDER BY cheapest_return_price ASC
        LIMIT :limit
    """

    cursor = mock_flight_db.cursor()
    cursor.execute(sql_query, query_plan["parameters"])
    result = cursor.fetchone()

    assert result is not None
    assert result["cheapest_return_price"] == 450.0
    assert result["currency_code"] == "SGD"
    assert result["session_id"] == "sess-001"
