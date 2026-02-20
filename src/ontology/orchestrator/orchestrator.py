"""Orchestrator service."""

from typing import Callable

from models.query_model import CompiledQuery, ExecutionResult, QueryPlan, QueryRequest, QueryResponse


class Orchestrator:
    """Coordinates planner, compiler, and executor modules."""

    def __init__(
        self,
        planner: Callable[[str], QueryPlan],
        validator: Callable[[QueryPlan], QueryPlan],
        normalizer: Callable[[QueryPlan], QueryPlan],
        compiler: Callable[[QueryPlan], CompiledQuery],
        executor: Callable[[CompiledQuery], ExecutionResult],
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._normalizer = normalizer
        self._compiler = compiler
        self._executor = executor

    def handle_query(self, request: QueryRequest) -> QueryResponse:
        plan = self._planner(request.nlq)
        if plan.missing_params:
            return QueryResponse(
                status="clarification_needed",
                intent=plan.intent,
                params=plan.params,
                missing_params=plan.missing_params,
                follow_up_question=plan.follow_up_question,
            )

        validated_plan = self._validator(plan)
        normalized_plan = self._normalizer(validated_plan)
        compiled = self._compiler(normalized_plan)
        execution = self._executor(compiled)

        return QueryResponse(
            status="success",
            intent=compiled.intent,
            params=compiled.bound_params,
            rows=execution.rows,
            sql=compiled.sql if request.include_debug else None,
        )
