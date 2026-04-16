"""Gemini API call — reads query_plan_prompt.j2, returns parsed JSON dict."""

from __future__ import annotations

import json
import time
from datetime import datetime

from google import genai
from google.genai import errors as genai_errors, types

from config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT_TEMPLATE

# If primary model is overloaded, try these in order
FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
MAX_RETRIES = 10
RETRY_DELAY = 3  # seconds between retries


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        return "\n".join(inner).strip()
    return text


def _call_model(client, model: str, prompt: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return response.text


def _build_history_block(history: list[tuple[str, dict]]) -> str:
    """Render the last ≤2 exchanges as a context block for the prompt."""
    if not history:
        return ""
    lines = ["Conversation history (use this to resolve references in the current question):"]
    for question, plan in history:
        intent = plan.get("intent", "unknown")
        params = plan.get("parameters", {})
        lines.append(f"  User said : {question}")
        lines.append(f"  Resolved  : intent={intent}, params={params}")
    lines.append("")  # blank line before current Question:
    return "\n".join(lines) + "\n"


def call_gemini(
    question: str,
    intents_str: str,
    param_schema_str: str,
    history: list[tuple[str, dict]] | None = None,
) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)

    template = PROMPT_TEMPLATE.read_text()
    prompt = template.format(
        history=_build_history_block(history or []),
        question=question,
        current_time=datetime.now().isoformat(timespec="seconds"),
        intents=intents_str,
        param_schema=param_schema_str,
    )

    models_to_try = [GEMINI_MODEL] + FALLBACK_MODELS

    for model in models_to_try:
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"  [llm] Calling {model} (attempt {attempt}/{MAX_RETRIES})...")
            try:
                raw = _strip_fences(_call_model(client, model, prompt))
                return json.loads(raw)
            except genai_errors.ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    raise EnvironmentError(
                        "Gemini API quota exceeded (free tier: 20 req/day). "
                        "Wait until tomorrow or add billing at https://ai.dev/rate-limit"
                    )
                raise
            except genai_errors.ServerError as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    if attempt < MAX_RETRIES:
                        print(f"  [llm] Model busy — retrying in {RETRY_DELAY}s...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"  [llm] {model} unavailable after {MAX_RETRIES} attempts — trying next model...")
                        break
                else:
                    raise
            except json.JSONDecodeError as e:
                raise ValueError(f"Gemini returned malformed JSON: {e}\n--- raw ---\n{raw}")

    raise RuntimeError("All Gemini models unavailable. Try again in a minute.")
