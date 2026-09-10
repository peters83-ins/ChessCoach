import pytest

from chesscoach.storage.coach import DEFAULT_PROFILE_ID, CoachRepository


def test_profiles_can_be_created_and_deleted(tmp_path):
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    assert [profile.profile_id for profile in repository.profiles()] == [DEFAULT_PROFILE_ID]
    created = repository.create_profile("  Tactics learner ", "student")
    assert created.name == "Tactics learner"
    assert any(profile.profile_id == "student" for profile in repository.profiles())
    assert repository.delete_profile("student") is True
    assert repository.delete_profile("student") is False


def test_profile_validation_protects_default_and_duplicates(tmp_path):
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    with pytest.raises(ValueError, match="empty"):
        repository.create_profile("  ")
    with pytest.raises(ValueError, match="reserved"):
        repository.create_profile("Other", DEFAULT_PROFILE_ID)
    repository.create_profile("Student", "student")
    with pytest.raises(ValueError, match="already exists"):
        repository.create_profile("Again", "student")
    with pytest.raises(ValueError, match="default"):
        repository.delete_profile(DEFAULT_PROFILE_ID)
