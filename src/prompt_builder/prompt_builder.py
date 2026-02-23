"""Prompt builder for NLQ planning."""

import json
from datetime import datetime, timezone

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import PromptBundle, PromptRequest


class PromptBuilder:
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

            output_format_instructions = {
                "required_output": {
                    "intent": "string",
                    "parameters": "object",
                    "missing_params": "array<string>",
                    "follow_up_question": "string|null",
                    "confidence": "number between 0 and 1",
                },
                "rules": [
                    "Return only valid JSON.",
                    "Do not include markdown fences.",
                    "Use an intent from the semantic whitelist only.",
                ],
            }

            current_time = datetime.now(timezone.utc).isoformat()
            prompt_context = {
                "semantic_whitelist": semantic_whitelist,
                "output_format_instructions": output_format_instructions,
            }

            user_message = request.prompt_template.format(
                question=request.question,
                current_time=current_time,
                semantic_model=json.dumps(prompt_context, ensure_ascii=False, indent=2),
            )

            bundle = PromptBundle(
                request_id=request.request_id,
                system_message=(
                    "You are an NLQ planner. Produce strictly valid JSON that matches the required schema "
                    "and only use intents/parameters from the semantic whitelist."
                ),
                user_message=user_message,
            )
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
