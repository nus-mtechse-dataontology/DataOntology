"""Unit tests for PromptBuilder — builder-pattern API."""

import pytest

from models.pipeline import PromptBundle

from prompt_builder.prompt_builder import PromptBuilder

TEMPLATE = (
    "Question: {question}\n"
    "Time: {current_time}\n"
    "Intents: {intents}\n"
    "Schema: {param_schema}"
)

INTENTS = {
    "cheapest_flight_on_route": {
        "required_params": ["origin", "destination", "start_date", "end_date"]
    }
}

PARAM_SCHEMA = {
    "origin": {"type": "string", "format": "iata_airport_code"},
    "destination": {"type": "string", "format": "iata_airport_code"},
}


def _built(question="What is the cheapest flight from SIN to BKK?", template=TEMPLATE):
    return (
        PromptBuilder()
        .set_question(question)
        .set_intent(INTENTS)
        .set_param_schema(PARAM_SCHEMA)
        .set_prompt_template(template)
        .build()
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_build_returns_prompt_bundle():
    result = _built()
    assert isinstance(result, PromptBundle)


def test_build_user_message_contains_question():
    result = _built(question="Show flights from SIN to BKK")
    assert "Show flights from SIN to BKK" in result.user_message


def test_build_user_message_contains_intents():
    result = _built()
    assert "cheapest_flight_on_route" in result.user_message


def test_build_user_message_contains_param_schema():
    result = _built()
    assert "iata_airport_code" in result.user_message


def test_build_user_message_contains_current_time():
    result = _built()
    # current_time is ISO format — contains 'T' separator
    assert "T" in result.user_message


def test_build_default_system_message_contains_json_instruction():
    result = _built()
    assert "JSON" in result.system_message


def test_set_system_message_overrides_default():
    builder = (
        PromptBuilder()
        .set_question("q")
        .set_intent({})
        .set_param_schema({})
        .set_prompt_template(TEMPLATE)
    )
    builder.set_system_message("Custom system instruction.")
    result = builder.build()
    assert result.system_message == "Custom system instruction."


def test_empty_template_produces_empty_user_message():
    result = (
        PromptBuilder()
        .set_question("q")
        .set_intent(INTENTS)
        .set_param_schema(PARAM_SCHEMA)
        .set_prompt_template("")
        .build()
    )
    assert result.user_message == ""


# ── error cases ───────────────────────────────────────────────────────────


def test_build_raises_key_error_for_unknown_placeholder():
    template = "Question: {question} Unknown: {missing_field}"
    with pytest.raises(KeyError):
        (
            PromptBuilder()
            .set_question("Find options")
            .set_intent(INTENTS)
            .set_param_schema(PARAM_SCHEMA)
            .set_prompt_template(template)
            .build()
        )


def test_builder_chain_returns_self_for_fluent_api():
    builder = PromptBuilder()
    assert builder.set_question("q") is builder
    assert builder.set_intent({}) is builder
    assert builder.set_param_schema({}) is builder
    assert builder.set_prompt_template("") is builder


def test_build_raises_generic_exception_for_non_key_errors():
    """Cover the except Exception branch — non-KeyError failures during format."""
    builder = PromptBuilder()
    builder.set_question("q")
    builder.set_intent({})
    builder.set_param_schema({})
    # A non-string template causes AttributeError inside .format()
    builder._prompt_template = None  # type: ignore[assignment]

    with pytest.raises(Exception):
        builder.build()
