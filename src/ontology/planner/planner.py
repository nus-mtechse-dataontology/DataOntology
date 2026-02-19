import logging

from models.query_model import QueryPlan


class Planner:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")

    def generate_plan(self, nlq: str, ontology_context: dict) -> QueryPlan:
        raise NotImplementedError
