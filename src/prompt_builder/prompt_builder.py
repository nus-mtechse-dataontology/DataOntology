import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import PromptBundle, PromptRequest


class PromptBuilder:
    def __init__(self, template_path: str | None = None) -> None:
        default_path = Path(__file__).with_name("templates").joinpath("query_plan_prompt.j2")
        self._template_path = Path(template_path) if template_path else default_path
        self._log = logging.getLogger("data_ontology")

    def _load_default_template(self) -> str:
        return self._template_path.read_text(encoding="utf-8")

    def build(self, request: PromptRequest) -> SuccessResponse[PromptBundle] | ErrorResponse:
        try:
            if not request.question.strip():
                return ErrorResponse(
                    request_id=request.request_id,
                    error=ErrorDetails(
                        code="invalid_question",
                        message="Question must not be empty.",
                        component="prompt_builder",
                    ),
                )

            intents = request.semantic_model.get("intents")
            if not isinstance(intents, dict):
                return ErrorResponse(
                    request_id=request.request_id,
                    error=ErrorDetails(
                        code="invalid_semantic_model",
                        message="Semantic model must contain an 'intents' object.",
                        component="prompt_builder",
                    ),
                )

            semantic_whitelist = {
                "intents": intents,
                "param_schema": request.semantic_model.get("param_schema", {}),
            }

            current_time = datetime.now(timezone.utc).isoformat()

            template = request.prompt_template.strip() or self._load_default_template()

            user_message = template.format(
                question=request.question,
                current_time=current_time,
                semantic_model=json.dumps({"semantic_whitelist": semantic_whitelist}, ensure_ascii=False, indent=2),
            )

            bundle = PromptBundle(
                request_id=request.request_id,
                system_message="You are an AI query planner. Return strictly valid JSON only.",
                user_message=user_message,
            )
            self._log.info("[%s] Prompt built", request.request_id)
            self._log.debug("[%s] system_message: %s", request.request_id, bundle.system_message)
            self._log.debug("[%s] user_message: %s", request.request_id, bundle.user_message)
            return SuccessResponse[PromptBundle](
                request_id=request.request_id,
                data=bundle,
            )

        except KeyError as error:
            return ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_prompt_template",
                    message="Prompt template is missing required placeholders.",
                    component="prompt_builder",
                    details={"missing_placeholder": str(error)},
                ),
            )
        except Exception as error:
            return ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="prompt_build_failed",
                    message="Unable to build prompt.",
                    component="prompt_builder",
                    details={"error": str(error)},
                ),
            )
