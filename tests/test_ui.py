import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from jarvis.core.stop_controller import StopController
from jarvis.ui.main_window import MainWindow


class FakeChatService:
    def __init__(self, response: str = "Test reply", failure: str | None = None) -> None:
        self.response = response
        self.failure = failure
        self.received_messages = []
        self.cancel_calls = 0

    def stream_reply(self, messages, cancellation_event):
        self.received_messages.append(tuple(messages))
        if self.failure is not None:
            from jarvis.chat.openai_chat import ChatServiceError

            raise ChatServiceError(self.failure)
        yield from (self.response[:5], self.response[5:])

    def cancel(self) -> None:
        self.cancel_calls += 1


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_stop_button_signals_cancellation_and_updates_status(self) -> None:
        controller = StopController()
        service = FakeChatService()
        window = MainWindow(controller, service)
        window.show()
        QTest.mouseClick(window.stop_button, Qt.MouseButton.LeftButton)

        self.assertTrue(controller.is_stopped)
        self.assertEqual(service.cancel_calls, 1)
        self.assertEqual(window.statusBar().currentMessage(), "STOP requested")
        window.close()

    def test_missing_api_key_is_shown_without_starting_a_request(self) -> None:
        window = MainWindow(api_key=None)
        window.show()
        window.message_input.setText("Hello")
        QTest.mouseClick(window.send_button, Qt.MouseButton.LeftButton)

        self.assertIn("OPENAI_API_KEY", window.statusBar().currentMessage())
        self.assertIsNone(window._chat_worker)
        self.assertEqual(window.transcript.toPlainText(), "")
        window.close()

    def test_chat_streams_reply_and_retains_conversation_context(self) -> None:
        service = FakeChatService("Hello from JARVIS")
        window = MainWindow(chat_service=service)
        window.show()
        window.message_input.setText("Hello")
        QTest.mouseClick(window.send_button, Qt.MouseButton.LeftButton)

        for _ in range(200):
            self.application.processEvents()
            if window._chat_worker is None:
                break
            QTest.qWait(10)

        self.assertIsNone(window._chat_worker)
        self.assertIn("You: Hello", window.transcript.toPlainText())
        self.assertIn("JARVIS: Hello from JARVIS", window.transcript.toPlainText())
        self.assertEqual(
            [(message.role, message.content) for message in window._messages],
            [("user", "Hello"), ("assistant", "Hello from JARVIS")],
        )
        self.assertEqual(
            [(message.role, message.content) for message in service.received_messages[0]],
            [("user", "Hello")],
        )
        self.assertEqual(window.statusBar().currentMessage(), "Ready")
        window.close()

    def test_chat_failure_is_visible_and_does_not_add_assistant_history(self) -> None:
        service = FakeChatService(failure="Test provider error")
        window = MainWindow(chat_service=service)
        window.show()
        window.message_input.setText("Hello")
        QTest.mouseClick(window.send_button, Qt.MouseButton.LeftButton)

        for _ in range(200):
            self.application.processEvents()
            if window._chat_worker is None:
                break
            QTest.qWait(10)

        self.assertIsNone(window._chat_worker)
        self.assertIn("[Error] Test provider error", window.transcript.toPlainText())
        self.assertEqual(window.statusBar().currentMessage(), "Test provider error")
        self.assertEqual(len(window._messages), 1)
        window.close()


if __name__ == "__main__":
    unittest.main()
