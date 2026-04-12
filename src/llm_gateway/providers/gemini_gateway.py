"""Gemini-backed LLM gateway implementation.

This provider adapts Gemini calls to the common ``LLMGateway`` interface used by
the orchestration pipeline. It returns standardized ``SuccessResponse`` and
``ErrorResponse`` payloads so upstream components can remain provider-agnostic.

Notes:
- Provider selection is resolved during application startup/factory wiring.
- This class only handles Gemini-specific auth/model/dependency behavior.
"""

import asyncio
import json
import os
import threading
import traceback
from concurrent.futures import TimeoutError as FutureTimeoutError

from pydantic_ai import Agent as PydanticAIAgent

from llm_gateway.llm_gateway import LLMGateway
from models.common import ErrorDetails, ErrorResponse
from models.pipeline import LLMRawResponse, NLQRequest


def _make_background_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    return loop


class GeminiGateway(LLMGateway):
    """Gemini provider implementation for ``LLMGateway``.

    The gateway executes prompts via ``pydantic-ai`` and normalizes outputs into
    the pipeline's ``LLMRawResponse`` contract.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self._bg_loop = _make_background_loop()
        """Initialize Gemini gateway configuration.

        Args:
            api_key: Gemini API key. If ``None``, runtime falls back to
                ``GEMINI_API_KEY``.
            model: Gemini model name. If ``None``, falls back to
                ``GEMINI_MODEL`` or ``gemini-3-flash-preview``.
            timeout_seconds: Max request duration before returning
                ``llm_timeout``.
        """
        super().__init__(
            api_key=api_key,
            model=model or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            timeout_seconds=timeout_seconds,
        )
        if self._api_key:
            os.environ.setdefault("GEMINI_API_KEY", self._api_key)

    def submit_prompt(
        self, bundle: NLQRequest
    ) -> LLMRawResponse | ErrorResponse:
        """Submit prompt bundle to Gemini and normalize response shape.

        Args:
            bundle: Prompt payload containing ``request_id``, ``system_message``,
                and ``user_message``.

        Returns:
            ``LLMRawResponse`` on successful generation, or
            ``ErrorResponse`` for validation/dependency/auth/timeout/runtime
            failures.

        Error codes produced:
            - ``missing_auth``: Gemini API key is unavailable.
            - ``missing_dependency``: ``pydantic-ai`` is not installed.
            - ``llm_timeout``: request exceeded configured timeout.
            - ``llm_auth_error``: provider returned auth-like failure.
            - ``llm_gateway_failed``: any other runtime/provider error.
        """
        try:
            api_key = self._api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                return ErrorResponse(
                    request_id=bundle.request_id,
                    error=ErrorDetails(
                        code="missing_auth",
                        message="GEMINI_API_KEY is required for GeminiGateway.",
                        component="llm_gateway",
                    ),
                )

            model_name = self._model
            if ":" not in model_name:
                model_name = f"google-gla:{model_name}"

            agent = PydanticAIAgent(model_name, system_prompt=bundle.system_message)

            future = asyncio.run_coroutine_threadsafe(
                agent.run(bundle.user_message), self._bg_loop
            )
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
                    message=self._timeout_message("Gemini"),
                    component="llm_gateway",
                ),
            )

        except Exception as error:
            message = str(error).strip() or "Gemini gateway call failed."
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
