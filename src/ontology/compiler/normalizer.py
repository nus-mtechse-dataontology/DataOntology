"""Query plan normalization."""
import logging

from models.query_model import QueryPlan


IATA_KEYS = {
    "origin",
    "destination",
    "outbound_origin",
    "outbound_destination",
    "return_origin",
    "return_destination",
}


class Normalizer:
    def __init__(self) -> None:
        self._log = logging.getLogger("data_ontology")

    def normalize_plan(self, plan: QueryPlan, current_date: str) -> QueryPlan:
        del current_date
        params = dict(plan.params)
        for key in IATA_KEYS:
            if key in params and isinstance(params[key], str):
                params[key] = params[key].upper()

        if "limit" not in params or params["limit"] is None:
            params["limit"] = 20
        else:
            params["limit"] = int(params["limit"])
        if int(params["limit"]) <= 0:
            raise ValueError("Parameter 'limit' must be > 0")

        return QueryPlan(
            intent=plan.intent,
            params=params,
            missing_params=list(plan.missing_params),
            follow_up_question=plan.follow_up_question,
            confidence=plan.confidence,
        )
