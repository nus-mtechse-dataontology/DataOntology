"""LLM gateway abstraction."""

from abc import ABC, abstractmethod

from models.common import ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse, PromptBundle


class LLMGateway(ABC):
    @abstractmethod
    def submit_prompt(
        self, bundle: PromptBundle
    ) -> SuccessResponse[LLMRawResponse] | ErrorResponse:
        raise NotImplementedError
