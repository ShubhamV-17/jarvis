"""Shared cancellation signal for active JARVIS operations."""

from threading import Event


class StopController:
    """Provides one cancellation event shared by the application runtime."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def cancellation_event(self) -> Event:
        return self._event

    @property
    def is_stopped(self) -> bool:
        return self._event.is_set()

    def stop(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()
