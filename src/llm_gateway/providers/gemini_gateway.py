import json
import os

try:
    from pydantic_ai import Agent as _PydanticAIAgent
except Exception:  # pragma: no cover
    _PydanticAIAgent = None

from llm_gateway.llm_gateway import LLMGateway
from models.pipeline import LLMRawResponse, PromptBundle


class GeminiGateway(LLMGateway):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self._api_key = api_key
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-3-flash")
        del timeout_seconds

    def submit_prompt(self, bundle: PromptBundle) -> LLMRawResponse:
        api_key = self._api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiGateway.")
        if _PydanticAIAgent is None:
            raise RuntimeError("pydantic-ai is required for GeminiGateway. Install dependency 'pydantic-ai'.")

        os.environ.setdefault("GEMINI_API_KEY", api_key)

        model_name = self._model
        if ":" not in model_name:
            model_name = f"google-gla:{model_name}"

        agent = _PydanticAIAgent(model_name, system_prompt=bundle.system_message)
        result = agent.run_sync(bundle.user_message)

        raw_text = getattr(result, "output", result)
        if isinstance(raw_text, str):
            text_output = raw_text
        else:
            text_output = json.dumps(raw_text, ensure_ascii=False)

        return LLMRawResponse(
            request_id=bundle.request_id,
            raw_response_text=text_output.strip(),
        )
