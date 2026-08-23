from __future__ import annotations

import ast
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "fixtures" / "browser" / "auth" / "antipattern-regression-map.json"
TEST_NAME_RE = re.compile(r"test_[a-zA-Z0-9_]+")


def _test_functions() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "tests").glob("test_browser*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names.update(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return names


def test_all_30_02c_antipatterns_have_honest_phase_ownership():
    document = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "browser-auth-antipattern-regression-map/0.1"
    assert document["slice"] == "BROWSER_SESSION_AUTH_RUNTIME_02C"
    entries = document["entries"]
    assert len(entries) == 30
    ids = [entry["id"] for entry in entries]
    assert ids == [f"B02C-AP-{index:03d}" for index in range(1, 31)]
    assert len(set(ids)) == 30
    assert sum(entry["status"] == "IMPLEMENTED" for entry in entries) == 22
    assert sum(entry["status"] == "PENDING" for entry in entries) == 8


def test_every_implemented_02c_a_guard_names_an_executable_test():
    document = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    available = _test_functions()
    for entry in document["entries"]:
        if entry["status"] == "PENDING":
            assert entry["guard"] is None
            continue
        assert entry["phase"] == "02C-A"
        guard = entry["guard"]
        assert isinstance(guard, str) and guard.strip()
        guard_tests = TEST_NAME_RE.findall(guard)
        assert guard_tests, entry["id"]
        missing = set(guard_tests) - available
        assert not missing, f"{entry['id']} names missing executable guards: {sorted(missing)}"
