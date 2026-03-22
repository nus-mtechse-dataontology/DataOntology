import json
import os
import sys
import tomllib
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_gateway.gateway_factory import LLMGatewayFactory
from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.providers.gemini_gateway import GeminiGateway
from llm_gateway.providers.openai_gateway import OpenAIGateway
from models.pipeline import PromptRequest
from ontology.semantic_model_loader import SemanticModelLoader
from prompt_builder.prompt_builder import PromptBuilder


def main():
    load_dotenv()

    config_path = Path(__file__).parent / "resources" / "config.toml"
    with open(config_path, "rb") as cf:
        config = tomllib.load(cf)

    llm_config = config.get("llm", {})
    providers_config = llm_config.get("providers", {})

    GatewayRegistry.register("gemini", GeminiGateway)
    GatewayRegistry.register("openai", OpenAIGateway)

    config_provider = llm_config.get("provider")
    llm_provider = os.getenv("LLM_PROVIDER") or config_provider
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    openai_model = os.getenv("OPENAI_MODEL")

    if llm_provider:
        provider = llm_provider
    else:
        detected = []
        if gemini_api_key:
            detected.append("gemini")
        if openai_api_key:
            detected.append("openai")

        if len(detected) == 1:
            provider = detected[0]
        elif len(detected) > 1:
            print(
                "Error: Multiple provider API keys detected but LLM_PROVIDER is not set. "
                "Set LLM_PROVIDER=gemini or LLM_PROVIDER=openai in .env."
            )
            return
        else:
            provider = "gemini"

    selected_provider_config = providers_config.get(provider, {})

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL") or selected_provider_config.get("model")
    if not api_key:
        if provider == "gemini":
            api_key = gemini_api_key
        elif provider == "openai":
            api_key = openai_api_key

    if not model:
        if provider == "gemini":
            model = gemini_model
        elif provider == "openai":
            model = openai_model

    timeout_raw = os.getenv("LLM_TIMEOUT")
    if timeout_raw is None:
        timeout_raw = str(selected_provider_config.get("timeout_seconds", llm_config.get("timeout_seconds", 30)))
    try:
        llm_timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        print(f"Error: Invalid timeout value '{timeout_raw}'.")
        return

    if not api_key:
        print(
            f"Error: Missing API key for provider '{provider}'. "
            "Set LLM_API_KEY or provider-specific key in .env."
        )
        return

    semantic_path = Path(__file__).parent / "src" / "ontology" / "semantic_layer_llm.json"
    loader = SemanticModelLoader()
    semantic_model = loader.load(str(semantic_path))

    question = "What is the cheapest return flight from Singapore to Bangkok in September 2019?"
    request = PromptRequest(
        request_id="debug-001",
        question=question,
        prompt_template="",
        semantic_model=semantic_model,
    )

    builder = PromptBuilder()
    build_response = builder.build(request)
    if build_response.status != "SUCCESS":
        print(f"Error: {build_response.error.message}")
        return

    prompt_bundle = build_response.data

    try:
        gateway = LLMGatewayFactory.create(
            provider=provider,
            api_key=api_key,
            model=model,
            timeout_seconds=llm_timeout_seconds,
        )
        llm_result = gateway.submit_prompt(prompt_bundle)

        if llm_result.status != "SUCCESS":
            print("Question:")
            print(question)
            print("\nLLM call failed:")
            print(f"Code: {llm_result.error.code}")
            print(f"Message: {llm_result.error.message}")
            print(f"Component: {llm_result.error.component}")
            return

        llm_response = llm_result.data

        print("Question:")
        print(question)
        print("\nRaw LLM response:")
        print(llm_response.raw_response_text)

        try:
            response_json = json.loads(llm_response.raw_response_text)
            print("\nParsed JSON:")
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print("\nLLM response is not valid JSON.")
    except Exception as e:
        print(f"Error calling {provider}: {e}")


if __name__ == "__main__":
    main()
