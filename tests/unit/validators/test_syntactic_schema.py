import pytest

from session.session import Session
from validators.syntactic.schema import QueryPlanPayload


def test_query_plan_payload_sets_defaults():
    payload = QueryPlanPayload(
        intent="cheapest_return_flight",
        parameters={"origin": "SIN"},
        confidence=0.9,
    )

    assert payload.intent == "cheapest_return_flight"
    assert payload.parameters == {"origin": "SIN"}
    assert payload.missing_params == []
    assert payload.follow_up_question is None
    assert payload.confidence == 0.9


def test_session_remains_abstract_but_subclasses_work():
    class DummySession(Session):
        def create_session(self):
            return "created"

    assert DummySession().create_session() == "created"
    with pytest.raises(TypeError):
        Session()
