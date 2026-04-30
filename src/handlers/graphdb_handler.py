from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails, ResultSet
from graphdb.service import GraphDBService

from pathlib import Path
import traceback


class GraphDBHandler(AbstractHandler):
    def __init__(
            self,
            graphdb_service: GraphDBService,
    ):
        super().__init__("GraphDBServiceHandler")
        self._graphdb_service = graphdb_service

    def handle(self, request: NLQRequest) -> NLQRequest | SuccessResponse | ErrorResponse:
        """
        Handles the 'prompt' request type. Passes request to the next handler down the chain if criteria
        not met for this handler.
        :param request: The NLQ request
        :return: SuccessResponse or ErrorResponse
        """
        if request.request_type == "general":
            result = self._graphdb_service.ask(request.question)
            request.request_type = "result"
            request.result_set = ResultSet(type_="general", request_id = request.request_id ,result_set=[{"answer": result}] if result else [])
        
        self._log.info("GraphDBHandler: Unable to process request: %s. Passing to next handler...", request.request_type)
        return super().handle(request)
    