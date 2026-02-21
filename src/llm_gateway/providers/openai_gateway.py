"""OpenAI-backed LLM gateway implementation placeholder."""

from llm_gateway.llm_gateway import LLMGateway
from models.pipeline import LLMRawResponse, PromptBundle


class OpenAIGateway(LLMGateway):
    def submit_prompt(self, bundle: PromptBundle) -> LLMRawResponse:
        raise NotImplementedError("OpenAI integration is not configured yet.")
