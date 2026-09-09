from pathlib import Path

from PySide6.QtCore import QSettings

from chesscoach.preferences import UserPreferences


def test_preferences_round_trip_and_analysis_presets(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    expected = UserPreferences("black", "high_contrast", 115, "deep", "both", False, "concise", 125)
    expected.save(settings)

    actual = UserPreferences.load(settings)
    assert actual == expected
    assert actual.engine_profile().name == "deep"
    assert actual.engine_profile().deep_time > UserPreferences().engine_profile().deep_time


def test_unknown_analysis_preset_uses_standard() -> None:
    assert UserPreferences(analysis_profile="unknown").engine_profile().name == "standard"
