"""Telegram webhook handler orchestration adapter."""

import logging
import re
from typing import Any
from datetime import datetime

from adapters.telegram import TelegramUpdateMapper
from adapters.telegram.interfaces import MessageClient
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.telegram_model import Update, Message
from orchestrator import Orchestrator



class TelegramWebhookHandler:
    def __init__(
        self,
        mapper: TelegramUpdateMapper,
        orchestrator: Orchestrator,
        client: MessageClient,
    ) -> None:
        self._mapper = mapper
        self._orchestrator = orchestrator
        self._client = client
        
        self._log = logging.getLogger("data_ontology")

    def handle(self, update: Update) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        self._log.info("Webhook Handler: Attempting to handle new message... ")
        
        if update.message:
            # check if text is a command or not.
            entities = update.message.entities
            self._safe_send_typing(update.message.chat.id, "")
            
            if entities:
                for entity in entities:
                    if entity.type_ == "bot_command":
                       return self._execute_commands(update.message, entity.offset, entity.length)
                    
            self._log.info("Not a bot command")
            return self._deliver_message(
                update.message.chat.id,
                "",
                f"Hello {update.message.from_user.first_name if update.message.from_user else ''}\\!\n\n"
                f"I am SIA Flight Bot, your trusty bot in searching flight info, destination fun and more\\! ✈️\n\n"
                f"I am afraid I could not recognise the command '{update.message.text}'\n\n"
                f"To start, simply send me a question such as the one below 👇\n\n"
                f"/flight What is the cheapest flight from Singapore to Bangkok in {datetime.now().strftime('%b %Y')}?"
            )
        else:
            if update.edited_message:
                self._safe_send_typing(update.edited_message.chat.id, "")
                return self._deliver_message(
                    update.edited_message.chat.id,
                    "",
                    f"Hello {update.edited_message.from_user.first_name if update.edited_message.from_user else ''}\\!\n\n"
                    f"I am afraid we do not support edited message at the moment\\! 😕\n\n"
                    f"To resume, simply send me a new question\\. ✈️"
                )
            
            return ErrorResponse(
                request_id="",
                error=ErrorDetails(
                    code="telegram_webhook_failed",
                    message="Unable to handler current request. Please try again later.",
                    component="telegram_webhook",
                ),
            )
    
    def _execute_commands(self, message: Message, offset: int, length: int):
        self._log.info("checking commands")
        command = message.text[offset: offset + length]
        
        match command:
            case "/start":
                return self._deliver_message(
                    message.chat.id,
                    "",
                    f"Hello {message.from_user.first_name if message.from_user else ''}\\!\n\n"
                    f"I am SIA Flight Bot, your trusty bot in searching flight info, destination fun and more\\! ✈️\n\n"
                    f"To start, simply send me a question such as the one below 👇\n\n"
                    f"/flight What is the cheapest flight from Singapore to Bangkok in {datetime.now().strftime('%b %Y')}?"
                )
            case "/flight":
                question = message.text[offset + length: ]
                
                if len(question) > 0:
                    nlq_request = self._mapper.map(question)
                    orchestration_response = self._orchestrator.handle_question(nlq_request)
                    # telegram_text = self._formatter.format(orchestration_response)
                    return self._deliver_message(
                        message.chat.id,
                        nlq_request.request_id,
                        orchestration_response.data if isinstance(orchestration_response, SuccessResponse) else orchestration_response.error.message
                    )
                
                self._log.info("Webhook Handler: Selected '/flight command, but no question asked...'")
                response = ("Oops\\! 🫣 Seems like you selected the /flight command\\.\n\n"
                            f"However, there is no question after the command\\. 😅\n\n"
                            f"To start, simply send me a question such as the one below 👇\n\n"
                            f"/flight What is the cheapest flight from Singapore to Bangkok in {datetime.now().strftime('%b %Y')}?")
                return self._deliver_message(message.chat.id, "", response)
            
            case "/general":
                nlq_request = self._mapper.map(message.text[offset + length:])
                nlq_request.request_type = "general"
                orchestration_response = self._orchestrator.handle_question(nlq_request)
                #telegram_text = self._formatter.format(orchestration_response)
                return self._deliver_message(message.chat.id,
                        nlq_request.request_id,
                        self._escape(orchestration_response.data['answer']) if isinstance(orchestration_response, SuccessResponse) else self._escape(orchestration_response.error.message))
            
            case "/help":
                help_text = (f"Hello {message.from_user.first_name if message.from_user else ''}\\!\n\n"
                             f"*To ask about flights:* ✈️\n\n"
                             f"/flight What is the cheapest flight from Singapore to Bangkok in "
                             f"{datetime.now().strftime('%b %Y')}?\n\n"
                             f"*To ask anything travel related:* 🏝️🌍\n\n"
                             f"/general What is the best time to visit Italy?")
                return self._deliver_message(message.chat.id, "", help_text)
            
            case _:
                return self._deliver_message(
                    message.chat.id,
                    "",
                    f"I am afraid I could not recognise the command '{command}'\n\n"
                    f"To start, simply send me a question such as the one below 👇\n\n"
                    f"/flight What is the cheapest flight from Singapore to Bangkok in {datetime.now().strftime('%b %Y')}?"
                )
    
    def _safe_send_typing(self, chat_id: int, request_id: str) -> None:
        try:
            self._client.send_typing(chat_id)
        except Exception as exc:
            self._log.warning(
                "[%s] send_typing failed for chat_id=%s: %s",
                request_id,
                chat_id,
                exc,
            )
            raise exc

    def _deliver_message(
        self,
        chat_id: int,
        request_id: str,
        text: str,
    ) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        try:
            self._client.send_message(chat_id, text)
        except Exception as exc:
            self._log.error(
                "[%s] send_message failed for chat_id=%s: %s",
                request_id,
                chat_id,
                exc,
            )
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="telegram_delivery_failed",
                    message=f"Failed to deliver Telegram message: {exc}",
                    component="telegram_webhook",
                ),
            )

        return SuccessResponse(
            request_id=request_id,
            data={"chat_id": chat_id, "delivered": True},
        )
        
    def _escape(self, text: str) -> str:
        escape_chars = r'_*[]()~`>#+-=|{}.!'
       
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)