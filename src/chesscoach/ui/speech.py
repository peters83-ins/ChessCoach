"""Optional local text-to-speech support with a silent fallback."""

from PySide6.QtCore import QObject

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # pragma: no cover - depends on the desktop Qt installation
    QTextToSpeech = None  # type: ignore[assignment,misc]


class SpeechService(QObject):
    """Speak local coach text when Qt's platform speech backend is installed."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._speech = QTextToSpeech(self) if QTextToSpeech is not None else None

    @property
    def available(self) -> bool:
        return self._speech is not None

    def speak(self, text: str) -> bool:
        if self._speech is None or not text.strip():
            return False
        self._speech.say(text)
        return True

    def stop(self) -> None:
        if self._speech is not None:
            self._speech.stop()
