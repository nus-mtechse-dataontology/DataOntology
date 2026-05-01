"""Load semantic_layer_v3.json and build the prompt context strings."""
import json
from graphdb.config import SEMANTIC_LAYER


def load_semantics() -> dict:
    with open(SEMANTIC_LAYER) as f:
        return json.load(f)


def build_prompt_context(semantics: dict) -> tuple[str, str]:
    """Return (intents_str, param_schema_str) ready to inject into the prompt template."""
    lines = []
    for name, intent in semantics["intents"].items():
        parts = [f"- {name}: {intent.get('description', '')}"]
        req = intent.get("required_params", [])
        opt = intent.get("optional_params", [])
        if req:
            parts.append(f"  required_params: {req}")
        if opt:
            parts.append(f"  optional_params: {opt}")
        examples = intent.get("examples", [])
        if examples:
            parts.append(f"  examples: {examples[:2]}")
        lines.append("\n".join(parts))

    intents_str = "\n\n".join(lines)
    param_schema_str = json.dumps(semantics["param_schema"], indent=2)
    return intents_str, param_schema_str
