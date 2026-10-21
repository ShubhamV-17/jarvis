"""Run JARVIS with ``python -m jarvis``."""

import logging
import sys

from PySide6.QtWidgets import QApplication

from jarvis.config import load_settings
from jarvis.database import initialize_database
from jarvis.logging_config import configure_logging
from jarvis.ui.main_window import MainWindow


def main() -> int:
    settings = load_settings()
    logger = configure_logging(settings.log_file, settings.log_level)
    logger.info("Starting JARVIS")
    initialize_database(settings.database_file)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    window = MainWindow(model=settings.model, api_key=settings.openai_api_key)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
