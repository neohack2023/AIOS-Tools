import json
from pathlib import Path


EXTENSION_ROOT = Path(__file__).parents[1] / "extensions" / "gemini-cli-aios"
EXPECTED_TOOLS = {
    "system_health",
    "canonical_hash_json",
    "validate_json_schema",
}


def test_manifest_exposes_only_slice_zero_read_only_tools() -> None:
    manifest = json.loads((EXTENSION_ROOT / "gemini-extension.json").read_text())

    assert manifest["name"] == "aios-tools"
    assert manifest["version"] == "0.2.0"
    assert manifest["contextFileName"] == "GEMINI.md"

    server = manifest["mcpServers"]["aios-tools"]
    assert server["command"] == "aios-tools-mcp"
    assert server["args"] == ["--transport", "stdio"]
    assert "trust" not in server
    assert set(server["includeTools"]) == EXPECTED_TOOLS


def test_extension_commands_are_namespaced_and_documented() -> None:
    commands = {
        path.relative_to(EXTENSION_ROOT / "commands").as_posix()
        for path in (EXTENSION_ROOT / "commands").rglob("*.toml")
    }

    assert commands == {
        "aios/hash-json.toml",
        "aios/health.toml",
        "aios/validate-schema.toml",
    }

    readme = (EXTENSION_ROOT / "README.md").read_text()
    assert "/aios:health" in readme
    assert "/aios:hash-json" in readme
    assert "/aios:validate-schema" in readme


def test_context_preserves_authority_and_write_boundary() -> None:
    context = (EXTENSION_ROOT / "GEMINI.md").read_text()

    assert "Gemini is a client of the governed runtime" in context
    assert "Notion owns architecture and governance authority" in context
    assert "GitHub owns live executable implementation" in context
    assert "Durable promotion requires" in context
    assert "Fail closed" in context
