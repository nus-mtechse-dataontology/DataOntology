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
import logging
import os
import threading
import time
import traceback
from concurrent.futures import TimeoutError as FutureTimeoutError

try:
    from pydantic_ai import Agent as _PydanticAIAgent
except Exception:  
    _PydanticAIAgent = None

from llm_gateway.llm_gateway import LLMGateway
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse, PromptBundle


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
        self._log = logging.getLogger("data_ontology")
        """Initialize Gemini gateway configuration.

        Args:
            api_key: Gemini API key. If ``None``, runtime falls back to
                ``GEMINI_API_KEY``.
            model: Gemini model name. If ``None``, falls back to
                ``GEMINI_MODEL`` or ``gemini-3-flash-preview``.
            timeout_seconds: Max request duration before returning
                ``llm_timeout``.
        """
        self._api_key = api_key
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self._timeout_seconds = timeout_seconds

    def submit_prompt(
        self, bundle: PromptBundle
    ) -> SuccessResponse[LLMRawResponse] | ErrorResponse:
        """Submit prompt bundle to Gemini and normalize response shape.

        Args:
            bundle: Prompt payload containing ``request_id``, ``system_message``,
                and ``user_message``.

        Returns:
            ``SuccessResponse[LLMRawResponse]`` on successful generation, or
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

            if _PydanticAIAgent is None:
                return ErrorResponse(
                    request_id=bundle.request_id,
                    error=ErrorDetails(
                        code="missing_dependency",
                        message="pydantic-ai is required for GeminiGateway.",
                        component="llm_gateway",
                    ),
                )

            os.environ.setdefault("GEMINI_API_KEY", api_key)

            model_name = self._model
            if ":" not in model_name:
                model_name = f"google-gla:{model_name}"

            self._log.info("[%s] Submitting prompt to Gemini model=%s", bundle.request_id, model_name)
            agent = _PydanticAIAgent(model_name, system_prompt=bundle.system_message)

            _start = time.monotonic()
            future = asyncio.run_coroutine_threadsafe(
                agent.run(bundle.user_message), self._bg_loop
            )
            result = future.result(timeout=self._timeout_seconds)
            elapsed = time.monotonic() - _start

            raw_text = getattr(result, "output", result)
            if isinstance(raw_text, str):
                text_output = raw_text
            else:
                text_output = json.dumps(raw_text, ensure_ascii=False)

            self._log.info("[%s] Gemini responded in %.2fs", bundle.request_id, elapsed)
            self._log.debug("[%s] LLM raw response: %s", bundle.request_id, text_output.strip())

            return SuccessResponse[LLMRawResponse](
                request_id=bundle.request_id,
                data=LLMRawResponse(
                    request_id=bundle.request_id,
                    raw_response_text=text_output.strip(),
                ),
            )

        except FutureTimeoutError:
            self._log.error("[%s] Gemini request timed out after %ds", bundle.request_id, self._timeout_seconds)
            return ErrorResponse(
                request_id=bundle.request_id,
                error=ErrorDetails(
                    code="llm_timeout",
                    message=f"Gemini request exceeded timeout of {self._timeout_seconds} seconds.",
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

            self._log.error("[%s] Gemini gateway error [%s]: %s", bundle.request_id, code, message)
            return ErrorResponse(
                request_id=bundle.request_id,
                error=ErrorDetails(
                    code=code,
                    message=message,
                    component="llm_gateway",
                    details={"exception_type": type(error).__name__, "trace": traceback.format_exc()},
                ),
            )
