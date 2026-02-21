"""Prompt builder for NLQ planning."""

from pathlib import Path

from models.pipeline import PromptBundle


class PromptBuilder:
    def __init__(self, template_path: str | None = None) -> None:
        if template_path is None:
            template_path = str(Path(__file__).with_name("templates").joinpath("query_plan_prompt.j2"))
        self._template_path = Path(template_path)

    def build(
        self,
        request_id: str,
        question: str,
        semantic_model: dict,
        current_time: str,
    ) -> PromptBundle:
        del request_id, question, semantic_model, current_time
        raise NotImplementedError("PromptBuilder.build is not implemented yet.")
