import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai import APIError

from jarvis.chat.openai_chat import (
    ChatMessage,
    ChatServiceError,
    OpenAIChatService,
)


class OpenAIChatServiceTests(unittest.TestCase):
    def test_streams_text_and_closes_stream_without_server_storage(self) -> None:
        class FakeStream:
            def __init__(self) -> None:
                self.close = Mock()
                self._events = iter(
                    [
                        SimpleNamespace(
                            type="response.output_text.delta", delta="Hello"
                        ),
                        SimpleNamespace(
                            type="response.output_text.delta", delta=" there"
                        ),
                        SimpleNamespace(type="response.completed"),
                    ]
                )

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._events)

        stream = FakeStream()
        client = Mock()
        client.responses.create.return_value = stream

        with patch("jarvis.chat.openai_chat.OpenAI", return_value=client):
            service = OpenAIChatService("test-key", "gpt-5-mini")
            chunks = list(
                service.stream_reply(
                    [ChatMessage(role="user", content="Hi")],
                    Event(),
                )
            )

        self.assertEqual(chunks, ["Hello", " there"])
        client.responses.create.assert_called_once_with(
            model="gpt-5-mini",
            input=[{"role": "user", "content": "Hi"}],
            stream=True,
            store=False,
        )
        stream.close.assert_called_once_with()

    def test_stream_errors_show_safe_provider_diagnostic(self) -> None:
        class FakeStream:
            def __init__(self) -> None:
                self.close = Mock()
                self._events = iter(
                    [
                        SimpleNamespace(
                            type="error",
                            code="invalid_api_key",
                            message="test-key sk-proj-secret-value is invalid",
                        )
                    ]
                )

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._events)

        stream = FakeStream()
        client = Mock()
        client.responses.create.return_value = stream
        with patch("jarvis.chat.openai_chat.OpenAI", return_value=client):
            service = OpenAIChatService("test-key", "gpt-5-mini")
            with self.assertRaises(ChatServiceError) as raised_error:
                list(
                    service.stream_reply(
                        [ChatMessage(role="user", content="Hi")],
                        Event(),
                    )
                )

        self.assertIn("invalid_api_key", str(raised_error.exception))
        self.assertNotIn("test-key", str(raised_error.exception))
        self.assertNotIn("sk-proj-secret-value", str(raised_error.exception))
        self.assertIn("[redacted API key]", str(raised_error.exception))
        stream.close.assert_called_once_with()

    def test_generic_api_error_shows_diagnostic_without_key(self) -> None:
        client = Mock()
        client.responses.create.side_effect = APIError(
            "Invalid model configuration",
            request=Mock(),
            body={"code": "invalid_model"},
        )
        with patch("jarvis.chat.openai_chat.OpenAI", return_value=client):
            service = OpenAIChatService("test-key", "gpt-5-mini")
            with self.assertRaises(ChatServiceError) as raised_error:
                list(
                    service.stream_reply(
                        [ChatMessage(role="user", content="Hi")],
                        Event(),
                    )
                )

        self.assertIn("invalid_model", str(raised_error.exception))
        self.assertIn("Invalid model configuration", str(raised_error.exception))
        self.assertNotIn("test-key", str(raised_error.exception))

    def test_missing_api_key_is_reported_without_creating_client(self) -> None:
        with patch("jarvis.chat.openai_chat.OpenAI") as openai_client:
            with self.assertRaisesRegex(ChatServiceError, "OPENAI_API_KEY"):
                OpenAIChatService(None, "gpt-5-mini")

        openai_client.assert_not_called()

    def test_cancelled_request_does_not_contact_provider(self) -> None:
        cancellation_event = Event()
        cancellation_event.set()
        with patch("jarvis.chat.openai_chat.OpenAI") as openai_client:
            service = OpenAIChatService("test-key", "gpt-5-mini")
            chunks = list(
                service.stream_reply(
                    [ChatMessage(role="user", content="Hi")],
                    cancellation_event,
                )
            )

        self.assertEqual(chunks, [])
        openai_client.return_value.responses.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
