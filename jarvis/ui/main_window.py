"""Main JARVIS desktop window."""

from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jarvis.chat.openai_chat import (
    ChatMessage,
    ChatServiceError,
    OpenAIChatService,
)
from jarvis.core.stop_controller import StopController
from jarvis.ui.chat_worker import ChatWorker, ChatService


class MainWindow(QMainWindow):
    def __init__(
        self,
        stop_controller: StopController | None = None,
        chat_service: ChatService | None = None,
        model: str = "gpt-5-mini",
        api_key: str | None = None,
    ) -> None:
        super().__init__()
        self._stop_controller = stop_controller or StopController()
        self._chat_service = chat_service
        self._model = model
        self._api_key = api_key
        self._messages: list[ChatMessage] = []
        self._current_response: list[str] = []
        self._chat_worker: ChatWorker | None = None

        self.setWindowTitle("JARVIS")
        self.resize(760, 540)

        heading = QLabel("JARVIS")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 30px; font-weight: 600;")

        self.transcript = QPlainTextEdit()
        self.transcript.setObjectName("chatTranscript")
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Your conversation will appear here.")
        self.transcript.setAccessibleName("Chat transcript")

        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setAccessibleName("Message")
        self.message_input.returnPressed.connect(self._send_message)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self._send_message)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addWidget(self.transcript, stretch=1)
        layout.addLayout(input_layout)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setAccessibleName("Stop current JARVIS operation")
        self.stop_button.setToolTip("Cancel the current JARVIS operation")
        self.stop_button.setStyleSheet(
            "QPushButton { background-color: #a83232; color: white; "
            "font-weight: bold; padding: 7px 18px; }"
            "QPushButton:hover { background-color: #c43c3c; }"
        )
        self.stop_button.clicked.connect(self._stop_current_operation)
        self.statusBar().showMessage("Ready")
        self.statusBar().addPermanentWidget(self.stop_button)

    def _send_message(self) -> None:
        text = self.message_input.text().strip()
        if not text or self._chat_worker is not None:
            return

        try:
            if self._chat_service is None:
                self._chat_service = OpenAIChatService(self._api_key, self._model)
        except ChatServiceError as error:
            self.statusBar().showMessage(str(error))
            return

        self._stop_controller.reset()
        self._messages.append(ChatMessage(role="user", content=text))
        self._current_response = []
        self.transcript.appendPlainText(f"You: {text}")
        self.transcript.appendPlainText("JARVIS: ")
        self.message_input.clear()
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.statusBar().showMessage("Thinking...")

        self._chat_worker = ChatWorker(
            self._chat_service,
            self._messages,
            self._stop_controller.cancellation_event,
        )
        self._chat_worker.chunk_received.connect(self._append_response_chunk)
        self._chat_worker.reply_completed.connect(self._finish_response)
        self._chat_worker.request_failed.connect(self._show_chat_error)
        self._chat_worker.request_cancelled.connect(self._finish_cancelled)
        self._chat_worker.finished.connect(self._chat_worker_finished)
        self._chat_worker.start()

    def _append_response_chunk(self, chunk: str) -> None:
        self._current_response.append(chunk)
        self.transcript.moveCursor(QTextCursor.MoveOperation.End)
        self.transcript.insertPlainText(chunk)
        self.transcript.ensureCursorVisible()

    def _finish_response(self, response: str) -> None:
        self._messages.append(ChatMessage(role="assistant", content=response))
        self.transcript.appendPlainText("")
        self.statusBar().showMessage("Ready")

    def _show_chat_error(self, message: str) -> None:
        self.transcript.appendPlainText(f"\n[Error] {message}")
        self.statusBar().showMessage(message)

    def _finish_cancelled(self) -> None:
        self.transcript.appendPlainText("\n[Response cancelled]")
        self.statusBar().showMessage("Response cancelled")

    def _chat_worker_finished(self) -> None:
        self._chat_worker = None
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.message_input.setFocus()

    def _stop_current_operation(self) -> None:
        self._stop_controller.stop()
        if self._chat_service is not None:
            self._chat_service.cancel()
        self.statusBar().showMessage("STOP requested")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_current_operation()
        if self._chat_worker is not None:
            self._chat_worker.wait(5000)
        super().closeEvent(event)
