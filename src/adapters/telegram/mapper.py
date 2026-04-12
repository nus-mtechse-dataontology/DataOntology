"""Map Telegram webhook updates into orchestration request contracts."""
import logging

from adapters.telegram.interfaces import UpdateMapper
from models.pipeline import NLQRequest
from models.telegram_model import Update


class TelegramUpdateMapper(UpdateMapper):
    def __init__(self,) -> None:
        self._log = logging.getLogger("data_ontology")
    
    def _build_nlq_request_from_update(self, update: Update) -> tuple[int, NLQRequest]:
        self._log.info("TelegramUpdateMapper: Building NLQ Request..")
       
        chat = update.message.chat
        text = update.message.text
        
        return chat.id, NLQRequest(question=text.strip())

    def map(self, update: Update) -> tuple[int, NLQRequest]:
        self._log.info("TelegramUpdateMapper: Attempting to map NLQ Request..")
        return self._build_nlq_request_from_update(update)
