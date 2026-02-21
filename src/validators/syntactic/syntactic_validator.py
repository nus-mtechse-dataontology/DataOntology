"""Syntactic validator for raw LLM output."""

from models.pipeline import LLMRawResponse, QueryPlan


class SyntacticValidator:
    def validate(self, raw_response: LLMRawResponse) -> QueryPlan:
        del raw_response
        raise NotImplementedError("SyntacticValidator.validate is not implemented yet.")
