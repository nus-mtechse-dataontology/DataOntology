import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from pydantic_ai import Agent as PydanticAIAgent

from llm_gateway.llm_gateway import LLMGateway
from models.common import ErrorDetails, ErrorResponse
from models.pipeline import LLMRawResponse, NLQRequest


class OpenAIGateway(LLMGateway):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
            timeout_seconds=timeout_seconds,
        )
        if self._api_key:
            os.environ.setdefault("OPENAI_API_KEY", self._api_key)

    def submit_prompt(
        self, bundle: NLQRequest
    ) -> LLMRawResponse | ErrorResponse:
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

            model_name = self._model
            if ":" not in model_name:
                model_name = f"openai:{model_name}"

            agent = PydanticAIAgent(model_name, system_prompt=bundle.system_message)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(agent.run_sync, bundle.user_message)
                result = future.result(timeout=self._timeout_seconds)

            raw_text = getattr(result, "output", result)
            if isinstance(raw_text, str):
                text_output = raw_text
            else:
                text_output = json.dumps(raw_text, ensure_ascii=False)

            return LLMRawResponse(raw_response_text=text_output.strip())

        except FutureTimeoutError:
            return ErrorResponse(
                request_id=bundle.request_id,
                error=ErrorDetails(
                    code="llm_timeout",
                    message=self._timeout_message("OpenAI"),
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
