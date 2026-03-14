import json
import os
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

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set. Add it to your .env file.")
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
        gateway = GeminiGateway(api_key=api_key)
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
        print(f"Error calling Gemini: {e}")


if __name__ == "__main__":
    main()
