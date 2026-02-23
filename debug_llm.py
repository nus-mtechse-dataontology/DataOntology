"""Debug script to test PromptBuilder + GeminiGateway with real LLM."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_gateway.providers.gemini_gateway import GeminiGateway
from models.pipeline import PromptRequest
from ontology.semantic_model_loader import SemanticModelLoader
from prompt_builder.prompt_builder import PromptBuilder


def main():
    load_dotenv()

    semantic_path = Path(__file__).parent / "src" / "ontology" / "semantic_layer_llm.json"

    loader = SemanticModelLoader()
    semantic_model = loader.load(str(semantic_path))

    prompt_template = """Question: {question}
Current time: {current_time}
Semantic model: {semantic_model}

Extract the intent and required parameters from the question above. Return strict JSON only."""

    question = "What is the cheapest return flight from Singapore to Bangkok in September 2019?"

    request = PromptRequest(
        request_id="debug-001",
        question=question,
        prompt_template=prompt_template,
        semantic_model=semantic_model,
    )

    print("\n" + "=" * 80)
    print("PROMPT BUILDING")
    print("=" * 80)
    print(f"Question: {question}\n")

    builder = PromptBuilder()
    build_response = builder.build(request)

    if build_response.status != "SUCCESS":
        print(f"Error: {build_response.error.message}")
        return

    prompt_bundle = build_response.data

    print("\nSystem Message:")
    print("-" * 80)
    print(prompt_bundle.system_message)

    print("\n\nUser Message (first 500 chars):")
    print("-" * 80)
    print(prompt_bundle.user_message[:500] + "...")

    print("\n\n" + "=" * 80)
    print("LLM GATEWAY")
    print("=" * 80)

    try:
        gateway = GeminiGateway()
        print("Submitting to Gemini LLM...\n")
        llm_response = gateway.submit_prompt(prompt_bundle)

        print("Raw LLM Response:")
        print("-" * 80)
        print(llm_response.raw_response_text)

        print("\n\nParsed Intent & Parameters:")
        print("-" * 80)
        response_json = json.loads(llm_response.raw_response_text)
        print(json.dumps(response_json, indent=2))

    except Exception as e:
        print(f"Error calling Gemini: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
