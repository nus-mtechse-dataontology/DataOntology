import logging

from models.query_model import CompiledQuery, QueryPlan


class SqlCompiler:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")


    def compile_to_sql(self, plan: QueryPlan, semantic_layer: dict) -> CompiledQuery:
        if not plan.intent:
            raise ValueError("Plan intent is required for SQL compilation.")

        intents = semantic_layer.get("intents", {})
        intent_spec = intents.get(plan.intent)
        if intent_spec is None:
            raise ValueError(f"Unknown intent: {plan.intent}")

        sql = intent_spec.get("sql_template")
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError(f"Intent '{plan.intent}' does not define a valid sql_template.")

        params = dict(plan.params)
        bound_params = {k: v for k, v in params.items() if f":{k}" in sql}
        return CompiledQuery(intent=plan.intent, sql=sql, bound_params=bound_params)
