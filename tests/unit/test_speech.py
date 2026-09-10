from chesscoach.ui.speech import SpeechService


def test_speech_service_is_safe_when_optional_backend_is_unavailable():
    service = SpeechService()
    assert isinstance(service.available, bool)
    assert service.speak("") is False
    if not service.available:
        assert service.speak("A short coaching note") is False
