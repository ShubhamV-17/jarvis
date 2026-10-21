"""Streaming text chat backed by OpenAI's Responses API."""

import logging
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from threading import Event, Lock
from typing import Literal

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
    Stream,
)
from openai.types.responses import ResponseStreamEvent

logger = logging.getLogger("jarvis.chat")

MessageRole = Literal["user", "assistant"]
API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: MessageRole
    content: str


class ChatServiceError(Exception):
    """Safe, user-facing error message from the chat service."""


class OpenAIChatService:
    def __init__(self, api_key: str | None, model: str) -> None:
        if not api_key:
            raise ChatServiceError(
                "OpenAI API key is missing. Add OPENAI_API_KEY to your .env file."
            )
        self._api_key = api_key
        self._model = model
        self._client = OpenAI(api_key=api_key, timeout=30.0)
        self._stream_lock = Lock()
        self._active_stream: Stream[ResponseStreamEvent] | None = None

    def _safe_diagnostic(self, message: str) -> str:
        diagnostic = message.replace(self._api_key, "[redacted]")
        diagnostic = API_KEY_PATTERN.sub("[redacted API key]", diagnostic)
        return diagnostic[:300]

    def cancel(self) -> None:
        with self._stream_lock:
            stream = self._active_stream
            self._active_stream = None
        if stream is not None:
            stream.close()

    def stream_reply(
        self,
        messages: Sequence[ChatMessage],
        cancellation_event: Event,
    ) -> Iterator[str]:
        if cancellation_event.is_set():
            return

        stream: Stream[ResponseStreamEvent] | None = None
        try:
            stream = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
                stream=True,
                store=False,
            )
            with self._stream_lock:
                self._active_stream = stream
            if cancellation_event.is_set():
                return
            for event in stream:
                if cancellation_event.is_set():
                    return
                if event.type == "response.output_text.delta":
                    yield event.delta
                elif event.type == "error":
                    message = self._safe_diagnostic(event.message)
                    code = f" ({event.code})" if event.code else ""
                    logger.warning("OpenAI stream error%s: %s", code, message)
                    raise ChatServiceError(f"OpenAI error{code}: {message}")
                elif event.type == "response.failed":
                    response_error = event.response.error
                    message = self._safe_diagnostic(response_error.message)
                    logger.warning(
                        "OpenAI response failed (%s): %s",
                        response_error.code,
                        message,
                    )
                    raise ChatServiceError(
                        f"OpenAI response failed ({response_error.code}): {message}"
                    )
        except ChatServiceError:
            raise
        except AuthenticationError as error:
            logger.warning("OpenAI authentication failed")
            raise ChatServiceError(
                "OpenAI authentication failed. Check OPENAI_API_KEY in your .env file."
            ) from error
        except RateLimitError as error:
            logger.warning("OpenAI rate limit or billing limit reached")
            raise ChatServiceError(
                "OpenAI rate limit or billing limit reached. Check your API usage."
            ) from error
        except (APIConnectionError, APITimeoutError) as error:
            logger.warning("OpenAI connection failed (%s)", type(error).__name__)
            raise ChatServiceError(
                "Could not connect to OpenAI. Check your internet connection and try again."
            ) from error
        except APIStatusError as error:
            message = self._safe_diagnostic(error.message)
            logger.warning(
                "OpenAI request failed with HTTP status %s (%s): %s",
                error.status_code,
                error.code or error.type or "unknown",
                message,
            )
            raise ChatServiceError(
                f"OpenAI returned HTTP {error.status_code} "
                f"({error.code or error.type or 'unknown'}): {message}"
            ) from error
        except APIError as error:
            message = self._safe_diagnostic(error.message)
            logger.warning(
                "OpenAI API error (%s): %s",
                error.code or error.type or type(error).__name__,
                message,
            )
            raise ChatServiceError(
                f"OpenAI API error ({error.code or error.type or 'unknown'}): {message}"
            ) from error
        except OpenAIError as error:
            logger.warning("OpenAI request failed (%s)", type(error).__name__)
            raise ChatServiceError(
                "OpenAI could not complete the request. Check your settings and try again."
            ) from error
        finally:
            if stream is not None:
                with self._stream_lock:
                    should_close = self._active_stream is stream
                    if should_close:
                        self._active_stream = None
                if should_close:
                    stream.close()
