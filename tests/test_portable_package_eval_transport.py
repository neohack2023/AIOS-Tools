from __future__ import annotations

import json
import zipfile
import urllib.request
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

from aios_tools.package_eval import (
    PortablePackageEvalError,
    advance_product_surface_receipt,
    build_eval_capsule,
    build_responses_payload,
    compile_package_context,
    execute_openai_pair,
    initialize_product_surface_receipt,
    validate_product_surface_receipt,
)
from aios_tools.package_eval import provider as provider_module


def _fixture(path: Path) -> Path:
    payload = {
        "fixture_version": "0.1",
        "fixture_id": "transport-fixture-01",
        "task_prompt": "Research when explicitly allowed, then return the required output.",
        "package_entry_instruction": "Follow the attached package working knowledge.",
        "allowed_tools": ["web_search"],
        "semantic_dimensions": ["instruction_following"],
        "deterministic_assertions": {
            "required_markers": ["STYLE PROMPT", "LYRICS"],
            "ordered_markers": ["STYLE PROMPT", "LYRICS"],
        },
        "product_surface": {
            "required": True,
            "lane": "CHATGPT_TEMPORARY_UNPERSONALIZED",
            "human_takeover_allowed": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SKILL.md", "# Test Skill\nUse exact output labels.")
        archive.writestr("knowledge/rules.txt", "STYLE PROMPT then LYRICS")
        archive.writestr("assets/pixel.png", b"\x89PNG\x00binary")
    return path


def test_context_projection_is_deterministic_and_text_only(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    first = compile_package_context(
        package_path=package,
        output_path=tmp_path / "first.txt",
    )
    second = compile_package_context(
        package_path=package,
        output_path=tmp_path / "second.txt",
    )
    text = first.output_path.read_text(encoding="utf-8")
    assert first.sha256 == second.sha256
    assert first.package_sha256 == second.package_sha256
    assert first.included_files[0] == "SKILL.md"
    assert "knowledge/rules.txt" in text
    assert "assets/pixel.png" not in text


def test_context_projection_rejects_archive_path_traversal(tmp_path: Path) -> None:
    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../escape.md", "bad")
    with pytest.raises(PortablePackageEvalError, match="unsafe package member"):
        compile_package_context(
            package_path=package,
            output_path=tmp_path / "context.txt",
        )


def test_responses_payload_is_stateless_and_package_is_only_on_delta() -> None:
    base = {
        "store": False,
        "allowed_tools": ["web_search"],
        "task_prompt": "Do the task",
        "package_entry_instruction": "Use package",
    }
    off = build_responses_payload(
        request_contract={**base, "treatment": "PACKAGE_OFF"},
        model="test-model",
        package_context=None,
    )
    on = build_responses_payload(
        request_contract={**base, "treatment": "PACKAGE_ON"},
        model="test-model",
        package_context="PACKAGE CONTEXT",
    )
    assert off["store"] is False and on["store"] is False
    assert off["model"] == on["model"] == "test-model"
    assert off["tools"] == on["tools"] == [{"type": "web_search"}]
    assert len(off["input"]) == 1
    assert len(on["input"]) == 2
    assert on["input"][0]["role"] == "developer"
    with pytest.raises(PortablePackageEvalError, match="may not receive package context"):
        build_responses_payload(
            request_contract={**base, "treatment": "PACKAGE_OFF"},
            model="test-model",
            package_context="leak",
        )


def test_provider_rejects_unadmitted_tool() -> None:
    with pytest.raises(PortablePackageEvalError, match="unsupported Responses tools"):
        build_responses_payload(
            request_contract={
                "store": False,
                "treatment": "PACKAGE_OFF",
                "allowed_tools": ["computer"],
                "task_prompt": "Do it",
            },
            model="test-model",
            package_context=None,
        )


def test_stubbed_pair_execution_writes_receipt_without_secret(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )
    calls: list[dict[str, object]] = []

    def transport(**kwargs):
        calls.append(kwargs["payload"])
        index = len(calls)
        text = (
            "plain baseline"
            if index == 1
            else "STYLE PROMPT\ncontrolled sound\nLYRICS\ncontrolled lyric"
        )
        return {
            "id": f"resp-{index}",
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }],
        }

    results = tmp_path / "results"
    receipt = execute_openai_pair(
        capsule_dir=capsule.output_dir,
        package_path=package,
        model="test-model",
        api_key="secret-test-key",
        output_dir=results,
        transport=transport,
    )
    assert len(calls) == 2
    assert calls[0]["store"] is False
    assert calls[1]["store"] is False
    assert receipt["deterministic_comparison"]["passed_check_delta"] > 0
    assert receipt["semantic_grade_status"] == "NOT_EXECUTED"
    receipt_schema = json.loads(
        (ROOT / "contracts/portable-package-eval-execution-receipt.v0.1.schema.json").read_text()
    )
    Draft202012Validator(receipt_schema).validate(receipt)
    persisted = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in results.iterdir()
        if p.is_file()
    )
    assert "secret-test-key" not in persisted


def test_product_surface_takeover_chain_and_secret_blackout(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )
    plan = json.loads(capsule.product_surface_plan_path.read_text())
    manifest = json.loads(capsule.manifest_path.read_text())
    receipt = initialize_product_surface_receipt(
        plan=plan,
        package_sha256=manifest["package"]["sha256"],
        fixture_sha256=manifest["fixture_sha256"],
    )
    for state in (
        "SESSION_PROVISIONING",
        "PACKAGE_ATTACHED",
        "PROMPT_SUBMITTED",
        "AUTH_REQUIRED",
        "USER_TAKEOVER",
        "VERIFY_PENDING",
        "AUTOMATION_RESUMED",
        "COMPLETED",
    ):
        receipt = advance_product_surface_receipt(
            receipt=receipt,
            next_state=state,
            evidence={"note": f"entered {state}"},
        )
    status = validate_product_surface_receipt(receipt)
    assert status == {"valid": True, "terminal": True, "state": "COMPLETED"}
    assert receipt["secret_input_model_visible"] is False
    receipt_schema = json.loads(
        (ROOT / "contracts/portable-package-product-surface-receipt.v0.1.schema.json").read_text()
    )
    Draft202012Validator(receipt_schema).validate(receipt)

    blocked = initialize_product_surface_receipt(
        plan=plan,
        package_sha256=manifest["package"]["sha256"],
        fixture_sha256=manifest["fixture_sha256"],
    )
    blocked = advance_product_surface_receipt(
        receipt=blocked,
        next_state="SESSION_PROVISIONING",
    )
    blocked = advance_product_surface_receipt(
        receipt=blocked,
        next_state="PACKAGE_ATTACHED",
    )
    blocked = advance_product_surface_receipt(
        receipt=blocked,
        next_state="PROMPT_SUBMITTED",
    )
    blocked = advance_product_surface_receipt(
        receipt=blocked,
        next_state="AUTH_REQUIRED",
    )
    with pytest.raises(PortablePackageEvalError, match="forbidden secret material"):
        advance_product_surface_receipt(
            receipt=blocked,
            next_state="USER_TAKEOVER",
            evidence={"password": "never-store-this"},
        )



def test_provider_transport_is_pinned_and_auth_is_unredirected(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"id":"resp-test","status":"completed","output":[]}'

    class FakeOpener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(provider_module.urllib.request, "build_opener", fake_build_opener)
    provider_module._post_json(
        endpoint=provider_module.DEFAULT_RESPONSES_ENDPOINT,
        api_key="secret-test-key",
        payload={"model": "test-model", "store": False, "input": []},
        timeout_seconds=1.0,
    )
    request = captured["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.unredirected_hdrs["Authorization"] == "Bearer secret-test-key"
    assert "Authorization" not in request.headers
    assert any(
        isinstance(handler, provider_module._NoRedirectHandler)
        for handler in captured["handlers"]
    )


def test_pair_execution_rejects_non_official_credential_endpoint(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )

    def transport(**kwargs):
        raise AssertionError("transport must not run for an untrusted endpoint")

    with pytest.raises(PortablePackageEvalError, match="pinned to the official Responses endpoint"):
        execute_openai_pair(
            capsule_dir=capsule.output_dir,
            package_path=package,
            model="test-model",
            api_key="secret-test-key",
            output_dir=tmp_path / "results",
            endpoint="https://example.invalid/v1/responses",
            transport=transport,
        )


def test_context_projection_rejects_total_zip_expansion_before_member_read(
    tmp_path: Path, monkeypatch
) -> None:
    package = tmp_path / "oversized.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("a.txt", "a" * 10)
        archive.writestr("b.txt", "b" * 10)

    original_open = zipfile.ZipFile.open

    def forbidden_open(self, *args, **kwargs):
        raise AssertionError("member data should not be opened after preflight size failure")

    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden_open)
    try:
        with pytest.raises(PortablePackageEvalError, match="exceeds max_total_bytes"):
            compile_package_context(
                package_path=package,
                output_path=tmp_path / "context.txt",
                max_total_bytes=15,
            )
    finally:
        monkeypatch.setattr(zipfile.ZipFile, "open", original_open)


def test_product_surface_secret_blackout_is_recursive(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )
    plan = json.loads(capsule.product_surface_plan_path.read_text())
    manifest = json.loads(capsule.manifest_path.read_text())
    receipt = initialize_product_surface_receipt(
        plan=plan,
        package_sha256=manifest["package"]["sha256"],
        fixture_sha256=manifest["fixture_sha256"],
    )
    receipt = advance_product_surface_receipt(
        receipt=receipt,
        next_state="SESSION_PROVISIONING",
    )
    with pytest.raises(PortablePackageEvalError, match="forbidden secret material"):
        advance_product_surface_receipt(
            receipt=receipt,
            next_state="PACKAGE_ATTACHED",
            evidence={
                "diagnostics": [
                    {"safe": "value"},
                    {"nested": {"api-key": "never-store-this"}},
                ]
            },
        )



def test_product_surface_validation_rejects_tampered_nested_secret(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )
    plan = json.loads(capsule.product_surface_plan_path.read_text())
    manifest = json.loads(capsule.manifest_path.read_text())
    receipt = initialize_product_surface_receipt(
        plan=plan,
        package_sha256=manifest["package"]["sha256"],
        fixture_sha256=manifest["fixture_sha256"],
    )
    receipt = advance_product_surface_receipt(
        receipt=receipt,
        next_state="SESSION_PROVISIONING",
        evidence={"note": "safe"},
    )
    receipt["events"][0]["evidence"] = {
        "nested": {"authorization": "Bearer never-store-this"}
    }
    with pytest.raises(PortablePackageEvalError, match="receipt contains forbidden secret material"):
        validate_product_surface_receipt(receipt)
