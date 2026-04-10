from compiler import SQLCompiler
from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails


class SQLCompilerHandler(AbstractHandler):
	def __init__(self, sql_compiler: SQLCompiler):
		super().__init__("SQLCompilerHandler")
		self._sql_compiler = sql_compiler
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'sql_compile' request. asses request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		if request.request_type == "sql_compile":
			self._log.info("SQLCompilerHandler: Compiling Query Plan...")
			self._load_semantics()
			
			if request.query_plan is not None:
				compiled_sql = self._sql_compiler.compile(request.query_plan, self._semantics)
				
				if isinstance(compiled_sql, ErrorResponse):
					self._log.error("SQLCompilerHandler: Failed to compile SQL...")
					self._log.error("SQLCompilerHandler: Error: %s", compiled_sql.error)
					return compiled_sql
				
				self._log.info("SQLCompilerHandler: Successfully compiled SQL, passing to next handler...")
				request.request_type = "sql_executor"
				request.compiled_sql = compiled_sql.data
				return super().handle(request)
			
			else:
				self._log.error("SQLCompilerHandler: Error: Requires SQL Compiler Handler, but QueryPlan is None.")
				ErrorResponse(
					request_id=request.request_id,
					error=ErrorDetails(
						code="SQLCompilerHandlerError",
						message="Requires SQL Compiler Handler, but QueryPlan is None",
						component=self._component_name,
						details={
							"error": "Handler Error. Requesting for SQL Compiler Handler, but QueryPlan is None."
						}
					)
				)
		
		self._log.info(
			"SQLCompilerHandler: Unable to process request: %s. Passing it to next handler...",
			request.request_type
		)
		return super().handle(request)
