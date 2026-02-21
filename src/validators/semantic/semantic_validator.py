"""Semantic validator against semantic model intents and required params."""

from models.pipeline import QueryPlan


class SemanticValidator:
    def validate(self, plan: QueryPlan, semantic_model: dict) -> QueryPlan:
        del plan, semantic_model
        raise NotImplementedError("SemanticValidator.validate is not implemented yet.")
