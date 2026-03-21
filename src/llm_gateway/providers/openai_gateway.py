import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

try:
    from pydantic_ai import Agent as _PydanticAIAgent
except Exception:
    _PydanticAIAgent = None

from llm_gateway.llm_gateway import LLMGateway
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse, PromptBundle


class OpenAIGateway(LLMGateway):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self._api_key = api_key
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
        self._timeout_seconds = timeout_seconds

    def submit_prompt(
        self, bundle: PromptBundle
    ) -> SuccessResponse[LLMRawResponse] | ErrorResponse:
        try:
            api_key = self._api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return ErrorResponse(
                    request_id=bundle.request_id,
                    error=ErrorDetails(
                        code="missing_auth",
                        message="OPENAI_API_KEY is required for OpenAIGateway.",
                        component="llm_gateway",
                    ),
                )

            if _PydanticAIAgent is None:
                return ErrorResponse(
                    request_id=bundle.request_id,
                    error=ErrorDetails(
                        code="missing_dependency",
                        message="pydantic-ai is required for OpenAIGateway.",
                        component="llm_gateway",
                    ),
                )

            os.environ.setdefault("OPENAI_API_KEY", api_key)

            model_name = self._model
            if ":" not in model_name:
                model_name = f"openai:{model_name}"

            agent = _PydanticAIAgent(model_name, system_prompt=bundle.system_message)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(agent.run_sync, bundle.user_message)
                result = future.result(timeout=self._timeout_seconds)

            raw_text = getattr(result, "output", result)
            if isinstance(raw_text, str):
                text_output = raw_text
            else:
                text_output = json.dumps(raw_text, ensure_ascii=False)

            return SuccessResponse[LLMRawResponse](
                request_id=bundle.request_id,
                data=LLMRawResponse(
                    request_id=bundle.request_id,
                    raw_response_text=text_output.strip(),
                ),
            )

        except FutureTimeoutError:
            return ErrorResponse(
                request_id=bundle.request_id,
                error=ErrorDetails(
                    code="llm_timeout",
                    message=f"OpenAI request exceeded timeout of {self._timeout_seconds} seconds.",
                    component="llm_gateway",
                ),
            )

        except Exception as error:
            message = str(error).strip() or "OpenAI gateway call failed."
            lowered = message.lower()
            if "timeout" in lowered:
                code = "llm_timeout"
            elif "auth" in lowered or "api key" in lowered or "permission" in lowered:
                code = "llm_auth_error"
            else:
                code = "llm_gateway_failed"

            return ErrorResponse(
                request_id=bundle.request_id,
                error=ErrorDetails(
                    code=code,
                    message=message,
                    component="llm_gateway",
                    details={"exception_type": type(error).__name__, "trace": traceback.format_exc()},
                ),
            )
