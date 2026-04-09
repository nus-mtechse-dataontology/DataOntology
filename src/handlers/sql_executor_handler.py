from execution import SQLExecutor
from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails


class SQLExecutorHandler(AbstractHandler):
	def __init__(self, sql_executor: SQLExecutor):
		super().__init__("SQLExecutorHandler")
		self._sql_executor = sql_executor
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'sql_executor' request. Passes request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		
		if request.request_type == "sql_executor":
			self._log.info("SQLExecutorHandler: Executing SQL Request...")
			if request.compiled_sql is not None:
				results = self._sql_executor.execute(request.compiled_sql)
				
				if isinstance(results, ErrorResponse):
					self._log.error("SQLExecutorHandler: Failed to generate response from DB...")
					self._log.error("SQLExecutorHandler: Error: %s", results.error)
					return results
				
				self._log.info("SQLExecutorHandler: Successfully generated response from DB, passing to next handler...")
				request.request_type = "result"
				request.result_set = results.data
				return super().handle(request)
			
			else:
				self._log.error("SQLExecutorHandler: Error: Requires SQL Executor Handler, but CompileQuery is None.")
				return ErrorResponse(
					request_id=request.request_id,
					error=ErrorDetails(
						code="SQLExecutorHandlerError",
						message="Requires SQL Executor Handler, but CompileQuery is None",
						component=self._component_name,
						details={
							"error": "Handler Error. Requesting for SQL Execution Handler, but CompiledQuery is None."
						}
					)
				)
		
		self._log.info(
			"SQLExecutorHandler: Unable to process request: %s. Passing it to next handler...",
			request.request_type
		)
		return super().handle(request)
