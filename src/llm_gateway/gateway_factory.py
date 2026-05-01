"""Factory for creating LLM gateway instances."""

from typing import Any
import logging

from llm_gateway.llm_gateway import LLMGateway
from llm_gateway.providers.gemini_gateway import GeminiGateway
from llm_gateway.providers.openai_gateway import OpenAIGateway


class LLMGatewayFactory:
    """Simple factory for creating Gemini or OpenAI gateway instances."""

    _PROVIDERS: dict[str, type[LLMGateway]] = {
        "gemini": GeminiGateway,
        "openai": OpenAIGateway,
    }
    
    _LOGGER = logging.getLogger("data_ontology")
    
    @classmethod
    def create(
        cls,
        config: dict[str, Any],
        **_: Any,
    ) -> LLMGateway:
        provider_name = (config.get("provider") or "gemini").lower()
        providers_config = config.get("providers", {})
        selected_provider_config = providers_config.get(provider_name, {})
        llm_api_key = selected_provider_config.get("api_key")
        llm_model = selected_provider_config.get("model")
        
        llm_timeout_raw = str(
            selected_provider_config.get(
                "timeout_seconds",
                config.get("timeout_seconds", 30),
            )
        )
        
        try:
            llm_timeout_seconds = int(llm_timeout_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid LLM timeout value: {llm_timeout_raw}") from exc
        
        gateway_class = cls._PROVIDERS.get(provider_name)

        if gateway_class is None:
            available = ", ".join(cls._PROVIDERS.keys())
            raise ValueError(
                f"Unknown LLM provider: '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        cls._LOGGER.info(
            "Created LLM gateway: provider=%s, model=%s, timeout_seconds=%s",
            provider_name,
            llm_model or "default",
            llm_timeout_seconds,
        )

        return gateway_class(
            api_key=llm_api_key,
            model=llm_model,
            timeout_seconds=llm_timeout_seconds,
        )
