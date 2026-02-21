"""Load and cache semantic model documents."""

import json
from functools import lru_cache
from pathlib import Path


class SemanticModelLoader:
    @lru_cache(maxsize=8)
    def load(self, path: str) -> dict:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Semantic file must be a JSON object: {path}")
        if "intents" not in payload or not isinstance(payload.get("intents"), dict):
            raise ValueError(f"Semantic file must include an 'intents' object: {path}")
        return payload

    def load_sql_semantic_model(self, path: str) -> dict:
        return self.load(path)

    def load_llm_semantic_model(self, path: str) -> dict:
        return self.load(path)
