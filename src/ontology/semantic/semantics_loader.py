import json
import logging
from functools import lru_cache
from pathlib import Path


class SemanticsLoader:
    def __init__(self) -> None:
        self._log = logging.getLogger("data_ontology")

    def load_semantic_layer(self, path: str) -> dict:
        return self._load_json(path)

    def load_semantic_layer_llm(self, path: str) -> dict:
        return self._load_json(path)

    @lru_cache(maxsize=8)
    def _load_json(self, path: str) -> dict:
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"Semantic file must be a JSON object: {path}")
        if "intents" not in payload or not isinstance(payload.get("intents"), dict):
            raise ValueError(f"Semantic file must include an 'intents' object: {path}")
        return payload
