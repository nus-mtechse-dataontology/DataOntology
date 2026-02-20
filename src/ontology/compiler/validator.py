import logging

from models.query_model import QueryPlan


class Validator:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")

    def validate(self, plan: QueryPlan, semantic_layer: dict) -> QueryPlan:
        """
        todo: Understand who is the caller and what is the content inside param: semantic_layer

        :param plan: The query plan
        :param semantic_layer: The semantic layer
        :return: The validated query plan
        """
        if not plan.intent:
            raise ValueError("Plan intent is required.")

        intents = semantic_layer.get("intents", {})
        if plan.intent not in intents:
            raise ValueError(f"Unknown intent: {plan.intent}")

        required = intents[plan.intent].get("required_params", [])
        missing = [k for k in required if plan.params.get(k) is None]
        if missing:
            raise ValueError(f"Missing required parameters for {plan.intent}: {', '.join(missing)}")

        return plan
