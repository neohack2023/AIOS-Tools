import json
from pathlib import Path

MAP_PATH = Path("fixtures/browser/antipattern-regression-map.json")


def test_all_22_harvested_antipatterns_have_explicit_regression_guards():
    document = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "browser-antipattern-regression-map/0.1"
    assert document["slice"] == "BROWSER_CORE_RUNTIME_02B"
    entries = document["entries"]
    assert len(entries) == 22
    ids = [entry["id"] for entry in entries]
    assert ids == [f"B02B-AP-{index:03d}" for index in range(1, 23)]
    assert len(set(ids)) == 22
    for entry in entries:
        assert isinstance(entry["hazard"], str) and entry["hazard"].strip()
        assert isinstance(entry["guard"], str) and entry["guard"].strip()
        assert "test" in entry["guard"].lower() or "regression" in entry["guard"].lower()
