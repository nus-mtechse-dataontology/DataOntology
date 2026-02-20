import logging


class LlmService:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")

    def call_llm(self, prompt: str):
        ...
