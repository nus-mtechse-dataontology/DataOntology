"""Compile a validated QueryPlan into SQL and bound parameters."""

from models.pipeline import CompiledSQL, QueryPlan


class SQLCompiler:
    def compile(self, plan: QueryPlan, semantic_model: dict) -> CompiledSQL:
        del plan, semantic_model
        raise NotImplementedError("SQLCompiler.compile is not implemented yet.")
