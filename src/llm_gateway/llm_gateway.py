"""LLM gateway abstraction."""

from abc import ABC, abstractmethod

from models.pipeline import NLQRequest
from models.common import ErrorResponse
from models.pipeline import LLMRawResponse


class LLMGateway(ABC):
    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: int = 30,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def _timeout_message(self, provider_name: str) -> str:
        return (
            f"{provider_name} request exceeded timeout of "
            f"{self._timeout_seconds} seconds."
        )

    @abstractmethod
    def submit_prompt(
        self, bundle: NLQRequest
    ) -> LLMRawResponse | ErrorResponse:
        raise NotImplementedError
