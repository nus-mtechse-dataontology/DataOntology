import argparse
import os
import sys
import tomllib
from pathlib import Path
from dotenv import load_dotenv



sys.path.insert(0, str(Path(__file__).parent / "src"))


def _load_runtime_symbols():
    from llm_gateway.gateway_factory import LLMGatewayFactory
    from models.pipeline import NLQRequest

    return LLMGatewayFactory, NLQRequest


def _load_config() -> dict:
    config_path = Path(__file__).parent / "resources" / "config.toml"
    with open(config_path, "rb") as cf:
        return tomllib.load(cf)


def _provider_settings(config: dict, provider: str) -> tuple[str | None, str | None, int]:
    llm_config = config.get("llm", {})
    providers = llm_config.get("providers", {})
    selected = providers.get(provider, {})

    api_key = selected.get("api_key")
    model = selected.get("model")
    timeout = selected.get("timeout_seconds", llm_config.get("timeout_seconds", 30))

    return api_key, model, int(timeout)


def _print_factory_checks(factory_cls) -> None:
    print("=== Factory checks ===")
    print("Expected providers: gemini, openai")

    for provider in ("gemini", "openai"):
        gateway = factory_cls.create(provider=provider)
        print(f"create('{provider}') -> {type(gateway).__name__}")

    try:
        factory_cls.create(provider="invalid-provider")
    except ValueError as exc:
        print(f"create('invalid-provider') -> expected error: {exc}")


def _run_live_gateway(
    factory_cls,
    request_cls,
    provider: str,
    api_key: str | None,
    model: str | None,
    timeout: int,
) -> None:
    print(f"\n=== Live gateway check: {provider} ===")

    gateway = factory_cls.create(
        provider=provider,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
    )

    bundle = request_cls(
        request_id=f"debug-{provider}",
        system_message="You are a helpful assistant. Keep response to one short sentence.",
        user_message="Say hello and include the provider name in your response.",
    )

    result = gateway.submit_prompt(bundle)
    if hasattr(result, "error") and getattr(result, "error") is not None:
        print(f"Status: ERROR ({result.error.code})")
        print(f"Message: {result.error.message}")
        return

    if hasattr(result, "raw_response_text"):
        print("Status: SUCCESS")
        print(f"Raw response: {result.raw_response_text}")
        return

    print(f"Unexpected result type: {type(result).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug LLM factory and gateways")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run real calls for configured providers",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "all"],
        default="all",
        help="Provider to live-test (default: all)",
    )
    args = parser.parse_args()

    load_dotenv()
    config = _load_config()

    try:
        (
            llm_gateway_factory,
            nlq_request,
        ) = _load_runtime_symbols()
    except Exception as exc:
        print("Unable to import runtime LLM modules.")
        print(f"Reason: {exc}")
        print("Install project dependencies and retry (notably pydantic-ai).")
        return

    _print_factory_checks(llm_gateway_factory)

    if not args.live:
        print("\nLive gateway checks skipped. Run with --live to test actual API calls.")
        return

    targets = ["gemini", "openai"] if args.provider == "all" else [args.provider]
    for provider in targets:
        api_key, model, timeout = _provider_settings(config, provider)

        # Respect explicit env overrides for local debugging without editing config.
        provider_key_env = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
        provider_model_env = "GEMINI_MODEL" if provider == "gemini" else "OPENAI_MODEL"
        api_key = os.getenv("LLM_API_KEY") or os.getenv(provider_key_env) or api_key
        model = os.getenv("LLM_MODEL") or os.getenv(provider_model_env) or model

        _run_live_gateway(
            llm_gateway_factory,
            nlq_request,
            provider,
            api_key,
            model,
            timeout,
        )


if __name__ == "__main__":
    main()
