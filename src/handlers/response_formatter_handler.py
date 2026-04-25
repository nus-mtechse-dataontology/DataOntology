from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails

from formatter.telegram_formatter import TelegramFormatter
from formatter.web_formatter import WebFormatter


class ResponseFormatterHandler(AbstractHandler):
	def __init__(self, formatters: dict[str, type]) -> None:
		super().__init__("ResponseFormatterHandler")
		self._formatter_instances: dict[str, TelegramFormatter | WebFormatter] = {
			name: cls() for name, cls in formatters.items()
		}
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		if request.request_type != "result":
			self._log.info(
				"ResponseBuilderHandler: Unable to process request: %s. Passing to next handler...",
				request.request_type,
			)
			return super().handle(request)
		
		self._log.info("ResponseBuilderHandler: Building Response...")
		
		# Validate result_set
		if request.result_set is None:
			self._log.error("ResponseBuilderHandler: ResultSet is None.")
			return self._build_error(request, "ResultSet is None.")
		
		# Retrieve formatter - single lookup, no match/case needed
		if (formatter := self._formatter_instances.get(request.source)) is None:
			self._log.error("ResponseBuilderHandler: Unknown source '%s'.", request.source)
			return self._build_error(request, f"Unknown source: {request.source!r}.")
		
		return formatter.format_response(request.result_set)
	
	def _build_error(self, request: NLQRequest, detail: str) -> ErrorResponse:
		return ErrorResponse(
			request_id=request.request_id,
			error=ErrorDetails(
				code="ResponseBuilderHandlerError",
				message=f"Requires Response Builder Handler, but {detail}",
				component=self._component_name,
				details={"error": f"Handler Error. Requesting for Response Builder Handler, but {detail}"},
			),
		)
