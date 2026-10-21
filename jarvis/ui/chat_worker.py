"""Background worker for streaming chat without blocking the desktop UI."""

import logging
from collections.abc import Iterator, Sequence
from threading import Event
from typing import Protocol

from PySide6.QtCore import QThread, Signal

from jarvis.chat.openai_chat import ChatMessage, ChatServiceError

logger = logging.getLogger("jarvis.ui.chat")


class ChatService(Protocol):
    def cancel(self) -> None:
        """Close any active provider stream."""

    def stream_reply(
        self,
        messages: Sequence[ChatMessage],
        cancellation_event: Event,
    ) -> Iterator[str]:
        """Yield response text chunks for the conversation."""


class ChatWorker(QThread):
    chunk_received = Signal(str)
    reply_completed = Signal(str)
    request_failed = Signal(str)
    request_cancelled = Signal()

    def __init__(
        self,
        service: ChatService,
        messages: Sequence[ChatMessage],
        cancellation_event: Event,
    ) -> None:
        super().__init__()
        self._service = service
        self._messages = tuple(messages)
        self._cancellation_event = cancellation_event

    def run(self) -> None:
        response_parts: list[str] = []
        try:
            for chunk in self._service.stream_reply(
                self._messages, self._cancellation_event
            ):
                if self._cancellation_event.is_set():
                    self.request_cancelled.emit()
                    return
                if chunk:
                    response_parts.append(chunk)
                    self.chunk_received.emit(chunk)
        except ChatServiceError as error:
            if self._cancellation_event.is_set():
                self.request_cancelled.emit()
                return
            self.request_failed.emit(str(error))
            return
        except Exception:
            if self._cancellation_event.is_set():
                self.request_cancelled.emit()
                return
            logger.exception("Unexpected chat failure")
            self.request_failed.emit(
                "An unexpected error interrupted the response. See the application log."
            )
            return

        if self._cancellation_event.is_set():
            self.request_cancelled.emit()
            return

        response = "".join(response_parts)
        if not response.strip():
            self.request_failed.emit("OpenAI returned an empty response. Please try again.")
            return
        self.reply_completed.emit(response)
