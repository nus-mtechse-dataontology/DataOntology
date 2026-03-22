"""Registry for managing available LLM gateway providers.

This module provides a central registry that maintains a lookup table of all
available LLM providers (Gemini, OpenAI, Claude, etc.) and their corresponding
gateway classes. The factory uses this registry to discover and instantiate
the appropriate gateway based on the provider name.

Typical usage:
    from llm_gateway.gateway_registry import GatewayRegistry
    from llm_gateway.providers.gemini_gateway import GeminiGateway
    
    # Register at startup
    GatewayRegistry.register("gemini", GeminiGateway)
    
    # Later, factory retrieves it
    gateway_class = GatewayRegistry.get("gemini")
"""

from typing import Dict, Type

from llm_gateway.llm_gateway import LLMGateway


class GatewayRegistry:
    """Registry for managing available LLM gateway providers.
    
    Central registry that maintains a lookup table of all available LLM providers
    and their corresponding gateway classes. Used by the factory to discover and
    instantiate the appropriate gateway based on provider name.
    
    Providers are registered once at startup and then can be retrieved by the factory.
    """
    
    _providers: Dict[str, Type[LLMGateway]] = {}
    
    @classmethod
    def register(cls, name: str, gateway_class: Type[LLMGateway]) -> None:
        """Register an LLM provider gateway.
        
        Adds a new LLM provider to the registry so it can be discovered and used
        by the factory. Called once at startup to register all available providers.
        
        Args:
            name: Provider name (e.g., 'gemini', 'openai', 'claude')
            gateway_class: Gateway class implementing LLMGateway interface
            
        Example:
            GatewayRegistry.register("gemini", GeminiGateway)
            GatewayRegistry.register("openai", OpenAIGateway)
        """
        cls._providers[name.lower()] = gateway_class
    
    @classmethod
    def get(cls, name: str) -> Type[LLMGateway] | None:
        """Retrieve a gateway class by provider name.
        
        Looks up the registered gateway class for the given provider name.
        Used by the factory to get the class it should instantiate.
        
        Args:
            name: Provider name (case-insensitive, e.g., 'gemini', 'openai')
            
        Returns:
            Gateway class if provider is registered, None otherwise
            
        Example:
            gateway_class = GatewayRegistry.get("openai")  # Returns OpenAIGateway
        """
        return cls._providers.get(name.lower())
    
    @classmethod
    def get_all(cls) -> Dict[str, Type[LLMGateway]]:
        """Get all registered providers.
        
        Returns a snapshot of all currently registered LLM providers.
        Useful for debugging, logging available options, or validation.
        
        Returns:
            Dictionary mapping provider names to their gateway classes
            
        Example:
            providers = GatewayRegistry.get_all()
            # Returns: {'gemini': GeminiGateway, 'openai': OpenAIGateway, ...}
        """
        return cls._providers.copy()
