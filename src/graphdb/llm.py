"""Gemini API call — reads query_plan_prompt.j2, returns parsed JSON dict."""
import json
import sys
import time
from datetime import datetime


def _progress(msg: str) -> None:
    """Print a progress line to stderr so it shows even when stdout is captured."""
    print(msg, file=sys.stderr, flush=True)

from google import genai
from google.genai import errors as genai_errors, types

from .config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT_TEMPLATE

# If primary model is overloaded, try these in order
FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
MAX_RETRIES = 40
RETRY_DELAY = 1   # seconds between retries — Gemma has no rate limit


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
        missing = plan.get("missing_params", [])
        lines.append(f"  User said : {question}")
        lines.append(f"  Resolved  : intent={intent}, params={params}")
        if missing:
            lines.append(f"  Still missing : {missing}")
            lines.append(f"  NOTE: The user's NEXT message is answering the follow-up for intent '{intent}'. Merge it with the params above — do NOT treat it as a new standalone question.")
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
            _progress(f"  [llm] Calling {model} (attempt {attempt}/{MAX_RETRIES})...")
            try:
                raw = _strip_fences(_call_model(client, model, prompt))
                _progress(f"  [llm] {model} responded OK")
                return json.loads(raw)
            except genai_errors.ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    raise EnvironmentError(
                        "Gemini API quota exceeded (free tier: 20 req/day). "
                        "Wait until tomorrow or add billing at https://ai.dev/rate-limit"
                    )
                raise
            except genai_errors.ServerError as e:
                err_str = str(e)
                is_retryable = any(code in err_str for code in ("503", "UNAVAILABLE", "500", "INTERNAL"))
                if is_retryable:
                    if attempt < MAX_RETRIES:
                        reason = "500 internal error" if "500" in err_str or "INTERNAL" in err_str else "model busy (503)"
                        _progress(f"  [llm] {reason} — retry {attempt}/{MAX_RETRIES} in {RETRY_DELAY}s...")
                        time.sleep(RETRY_DELAY)
                    else:
                        _progress(f"  [llm] {model} failed after {MAX_RETRIES} attempts — trying next model...")
                        break
                else:
                    raise
            except json.JSONDecodeError as e:
                raise ValueError(f"Gemini returned malformed JSON: {e}\n--- raw ---\n{raw}")

    raise RuntimeError("All Gemini models unavailable. Try again in a minute.")
