"""Abstract interfaces for the Telegram adapter layer."""

from abc import ABC, abstractmethod
from typing import Any

from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


class UpdateMapper(ABC):
    @abstractmethod
    def map(self, update: dict[str, Any]) -> tuple[int, NLQRequest] | ErrorResponse:
        pass


class MessageClient(ABC):
    @abstractmethod
    def send_message(self, chat_id: int, text: str) -> None:
        pass

    @abstractmethod
    def send_typing(self, chat_id: int) -> None:
        pass


class ResponseFormatter(ABC):
    @abstractmethod
    def format(self, response: SuccessResponse[QuestionResponse] | ErrorResponse) -> str:
        pass
