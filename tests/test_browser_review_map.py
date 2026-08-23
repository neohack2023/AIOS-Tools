import json
from pathlib import Path

MAP_PATH = Path("fixtures/browser/review-regression-map.json")
PYPROJECT = Path("pyproject.toml")


def test_rowan_review_findings_have_explicit_regression_ownership():
    document = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "browser-review-regression-map/0.1"
    assert document["slice"] == "BROWSER_CORE_RUNTIME_02B"
    assert document["reviewer"] == "PERS-BROWSER-01"
    entries = document["entries"]
    assert [entry["id"] for entry in entries] == [f"B02B-RV-{index:03d}" for index in range(1, 11)]
    for entry in entries:
        assert entry["finding"].strip()
        assert entry["guard"].startswith("tests/")


def test_playwright_dependency_is_pinned_to_validated_version():
    project = PYPROJECT.read_text(encoding="utf-8")
    assert '"playwright==1.62.0"' in project
