import pytest

from chesscoach.courses.catalog import CourseCatalog, CourseCatalogError


def payload(line=("e2e4", "e7e5", "g1f3")):
    return {
        "schema_version": 1,
        "courses": [
            {
                "id": "demo",
                "version": 1,
                "title": "Demo Opening",
                "description": "A short course",
                "level_min": 600,
                "level_max": 1400,
                "side": "white",
                "estimated_minutes": 10,
                "modules": [{"id": "m1", "title": "Start", "summary": "", "exercise_ids": ["e1"]}],
                "exercises": [
                    {
                        "id": "e1",
                        "module_id": "m1",
                        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                        "learner_color": "white",
                        "line": list(line),
                        "prompt": "Develop a piece",
                    }
                ],
            }
        ],
    }


def test_catalog_validates_and_filters_courses():
    catalog = CourseCatalog.from_data(payload())
    assert catalog.courses[0].exercise("e1").line == ("e2e4", "e7e5", "g1f3")
    assert catalog.search("opening", side="white", level=800)[0].id == "demo"
    assert catalog.search("missing") == ()


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"courses": {}},
    ],
)
def test_catalog_rejects_bad_schema(change):
    data = payload()
    data.update(change)
    with pytest.raises(CourseCatalogError):
        CourseCatalog.from_data(data)


def test_catalog_rejects_illegal_move():
    with pytest.raises(CourseCatalogError, match="Illegal move"):
        CourseCatalog.from_data(payload(("e2e5",)))


def test_catalog_rejects_more_than_two_learner_decisions():
    with pytest.raises(CourseCatalogError, match="exceeds two"):
        CourseCatalog.from_data(payload(("e2e4", "e7e5", "g1f3", "b8c6", "f1c4")))
