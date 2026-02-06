from app.models.query_plan import QueryPlan

class Planner:
    def generate_plan(self, nlq: str, ontology_context: dict) -> QueryPlan:
        raise NotImplementedError
