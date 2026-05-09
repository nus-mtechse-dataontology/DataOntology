import pytest
from unittest.mock import MagicMock, patch
from graphdb.llm import _strip_fences, _build_history_block, call_gemini

def test_strip_fences():
    # With fences
    text = "```json\n{\"key\": \"value\"}\n```"
    assert _strip_fences(text) == '{"key": "value"}'
    
    # Without fences
    text = '{"key": "value"}'
    assert _strip_fences(text) == '{"key": "value"}'
    
    # Only starting fence
    text = "```\n{\"key\": \"value\"}"
    assert _strip_fences(text) == '{"key": "value"}'

def test_build_history_block():
    # No history
    assert _build_history_block([]) == ""
    
    # With history
    history = [
        ("What is the cheapest flight to BKK?", {"intent": "cheapest_flight", "parameters": {"dest": "BKK"}, "missing_params": []})
    ]
    block = _build_history_block(history)
    assert "Conversation history" in block
    assert "User said : What is the cheapest flight to BKK?" in block
    assert "intent=cheapest_flight" in block

@patch("src.graphdb.llm.genai.Client")
@patch("src.graphdb.llm.PROMPT_TEMPLATE")
def test_call_gemini_success(mock_template, mock_client_class):
    # Setup mocks
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_template.read_text.return_value = "Prompt: {history} {question} {current_time} {intents} {param_schema}"
    
    mock_response = MagicMock()
    mock_response.text = '{"intent": "test_intent", "parameters": {}, "confidence": 0.9}'
    mock_client.models.generate_content.return_value = mock_response
    
    result = call_gemini("Hello", "intents", "schema")
    
    assert result["intent"] == "test_intent"
    mock_client.models.generate_content.assert_called_once()

@patch("src.graphdb.llm.genai.Client")
@patch("src.graphdb.llm.PROMPT_TEMPLATE")
def test_call_gemini_json_error(mock_template, mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_template.read_text.return_value = "Prompt: {history} {question} {current_time} {intents} {param_schema}"
    
    mock_response = MagicMock()
    mock_response.text = "Not JSON"
    mock_client.models.generate_content.return_value = mock_response
    
    with pytest.raises(ValueError, match="malformed JSON"):
        call_gemini("Hello", "intents", "schema")
