"""Factory for creating LLM gateway instances."""

from typing import Any

from llm_gateway.llm_gateway import LLMGateway
from llm_gateway.providers.gemini_gateway import GeminiGateway
from llm_gateway.providers.openai_gateway import OpenAIGateway


class LLMGatewayFactory:
    """Simple factory for creating Gemini or OpenAI gateway instances."""

    _PROVIDERS: dict[str, type[LLMGateway]] = {
        "gemini": GeminiGateway,
        "openai": OpenAIGateway,
    }
    
    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
        **_: Any,
    ) -> LLMGateway:
        provider_name = provider.lower()
        gateway_class = cls._PROVIDERS.get(provider_name)

        if gateway_class is None:
            available = ", ".join(cls._PROVIDERS.keys())
            raise ValueError(
                f"Unknown LLM provider: '{provider}'. "
                f"Available providers: {available}"
            )

        return gateway_class(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )
