"""LLM gateway abstraction."""

from abc import ABC, abstractmethod

from models import NLQRequest
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse


class LLMGateway(ABC):
    @abstractmethod
    def submit_prompt(
        self, bundle: NLQRequest
    ) -> LLMRawResponse | ErrorResponse:
        raise NotImplementedError
