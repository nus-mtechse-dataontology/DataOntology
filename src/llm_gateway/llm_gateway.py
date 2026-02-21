"""LLM gateway abstraction."""

from abc import ABC, abstractmethod

from models.pipeline import LLMRawResponse, PromptBundle


class LLMGateway(ABC):
    @abstractmethod
    def submit_prompt(self, bundle: PromptBundle) -> LLMRawResponse:
        raise NotImplementedError
