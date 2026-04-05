import json
from datetime import datetime, timezone
import logging
from typing import Any
import traceback

from models import PromptBundle


class PromptBuilder:
    def __init__(self) -> None:
        self._prompt_template = ""
        self._intents = {}
        self._param_schema = {}
        self._question = ""
        self._system_message = "You are an AI query planner. Return strictly valid JSON only."
        self._log = logging.getLogger("data_ontology")
    
    def set_question(self, question: str):
        self._question = question
        return self
    
    def set_system_message(self, system_message: str):
        self._system_message = system_message
    
    def set_prompt_template(self, prompt: str):
        self._prompt_template = prompt
        return self
   
    def set_intent(self, intents: dict[str, Any]):
        self._intents = intents
        return self
    
    def set_param_schema(self, param_schema: dict[str, Any]):
        self._param_schema = param_schema
        return self
    
    def build(self) -> PromptBundle:
        try:
            current_time = datetime.now(timezone.utc).isoformat()
  
            return PromptBundle(
                system_message=self._system_message,
                user_message=(
                    self._prompt_template
                    .format(
                        question=self._question,
                        current_time=current_time,
                        intents=json.dumps(self._intents, ensure_ascii=False, indent=2),
                        param_schema=json.dumps(self._param_schema, ensure_ascii=False, indent=2)
                    )
                )
            )
        
        except KeyError as error:
            self._log.error("PromptBuilder: Key Error when formatting prompt: %s", error)
            self._log.error(traceback.format_exc())
            raise KeyError("Unable to format prompt due to missing keys.") from error
        
        except Exception as error:
            self._log.error("PromptBuilder: Unexpected Error when building prompt: %s", error)
            self._log.error(traceback.format_exc())
            raise Exception(str(error)) from error
