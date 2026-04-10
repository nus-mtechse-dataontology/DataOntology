"""Factory for creating LLM gateway instances.

This module provides a factory pattern for instantiating the correct LLM gateway
based on provider name. It uses the GatewayRegistry to discover available providers
and handles provider-specific configuration.

Typical usage:
    from llm_gateway.gateway_factory import LLMGatewayFactory
    
    # Create with explicit provider
    gateway = LLMGatewayFactory.create(
        provider="openai",
        api_key="sk-...",
        model="gpt-4",
        timeout_seconds=30
    )
    
    # Create from environment variables
    gateway = LLMGatewayFactory.create_from_config()
"""

import os
from typing import Any

from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.llm_gateway import LLMGateway
from models.common import ErrorDetails, ErrorResponse


class LLMGatewayFactory:
    """Factory for creating LLM gateway instances.
    
    Provides methods to instantiate gateway implementations based on provider name.
    Supports both explicit configuration and environment variable-based configuration.
    """
    
    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
        **kwargs: Any,
    ) -> LLMGateway:
        """Create an LLM gateway instance.
        
        Instantiates the gateway class registered for the given provider name
        and passes the configuration parameters to its constructor.
        
        Args:
            provider: Provider name (e.g., 'gemini', 'openai', 'claude')
            api_key: API key for the provider (optional, can use env vars)
            model: Model name/ID for the provider (optional)
            timeout_seconds: Request timeout in seconds (default: 30)
            **kwargs: Additional provider-specific configuration
            
        Returns:
            Instantiated gateway ready to use
            
        Raises:
            ValueError: If provider is not registered
            
        Example:
            gateway = LLMGatewayFactory.create(
                provider="openai",
                api_key="sk-...",
                model="gpt-4"
            )
        """
        gateway_class = GatewayRegistry.get(provider)
        
        if gateway_class is None:
            available = ", ".join(GatewayRegistry.get_all().keys())
            raise ValueError(
                f"Unknown LLM provider: '{provider}'. "
                f"Available providers: {available or 'none registered'}"
            )
        
        return gateway_class(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )
    
    @classmethod
    def create_from_config(self, **overrides: Any) -> LLMGateway:
        """Create an LLM gateway from environment variables.
        
        Reads provider configuration from environment variables:
        - LLM_PROVIDER: Provider name (required, default: 'gemini')
        - LLM_API_KEY: API key for the provider (optional)
        - LLM_MODEL: Model name/ID (optional)
        - LLM_TIMEOUT: Request timeout in seconds (optional, default: 30)
        
        Additional provider-specific env vars are passed as kwargs.
        
        Args:
            **overrides: Override specific configuration values programmatically
                        (takes precedence over environment variables)
        
        Returns:
            Instantiated gateway configured from environment
            
        Raises:
            ValueError: If required environment variables are missing or invalid
            
        Example:
            # With environment: export LLM_PROVIDER=openai
            gateway = LLMGatewayFactory.create_from_config()
            
            # With overrides
            gateway = LLMGatewayFactory.create_from_config(
                api_key="custom-key"
            )
        """
        provider = overrides.get("provider") or os.getenv("LLM_PROVIDER", "gemini")
        api_key = overrides.get("api_key") or os.getenv("LLM_API_KEY")
        model = overrides.get("model") or os.getenv("LLM_MODEL")
        timeout_str = overrides.get("timeout_seconds") or os.getenv("LLM_TIMEOUT", "30")
        
        try:
            timeout_seconds = int(timeout_str)
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid LLM_TIMEOUT value: '{timeout_str}'. Must be an integer."
            )
        
        return self.create(
            provider=provider,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    
    @classmethod
    def get_available_providers(cls) -> dict[str, type]:
        """Get all registered provider names and classes.
        
        Returns:
            Dictionary mapping provider names to gateway classes
            
        Example:
            providers = LLMGatewayFactory.get_available_providers()
            # Returns: {'gemini': GeminiGateway, 'openai': OpenAIGateway}
        """
        return GatewayRegistry.get_all()
