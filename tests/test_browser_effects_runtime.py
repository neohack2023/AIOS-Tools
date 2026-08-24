from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

import pytest

pytest.importorskip("playwright")

from aios_tools.browser.effects_runtime import mutate_request_async, mutate_reversible_async, upload_execute_async
from aios_tools.browser.mutation import MutationLedger, build_mutation_grant, mutation_contract_fingerprint
from aios_tools.browser.uploads import (
    ArtifactDescriptor,
    ArtifactRef,
    SyntheticArtifactResolver,
)


class _State:
    def __init__(self):
        self.value = 0
        self.uploads = 0
        self.extra_mutations = 0


class _Handler(BaseHTTPRequestHandler):
    state: _State

    def log_message(self, format, *args):
        return

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/state":
            self._json(200, {"value": self.state.value, "uploads": self.state.uploads})
            return
        if path == "/upload":
            body = b"""<!doctype html>
<html><body>
<label for="fixture-file">Fixture file</label>
<input id="fixture-file" type="file" style="display:none">
<script>
document.getElementById('fixture-file').addEventListener('change', async () => {
  const file = document.getElementById('fixture-file').files[0];
  const form = new FormData();
  form.append('file', file);
  await fetch('/upload-target', {method: 'POST', body: form});
});
</script>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/upload-double":
            body = b"""<!doctype html>
<html><body>
<label for="fixture-file">Fixture file</label>
<input id="fixture-file" type="file" style="display:none">
<script>
document.getElementById('fixture-file').addEventListener('change', async () => {
  const file = document.getElementById('fixture-file').files[0];
  const form = new FormData();
  form.append('file', file);
  await fetch('/upload-target', {method: 'POST', body: form});
  await fetch('/second-target', {method: 'POST', body: 'should-block'});
});
</script>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(404, {"error": "not-found"})

    def _mutation(self):
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        if path == "/mutate":
            self.state.value += 1
            self._json(200, {"ok": True})
            return
        if path == "/rollback":
            self.state.value = 0
            self._json(200, {"ok": True})
            return
        if path == "/upload-target":
            self.state.uploads += 1
            self._json(201, {"ok": True})
            return
        if path == "/second-target":
            self.state.extra_mutations += 1
            self._json(201, {"ok": True})
            return
        self._json(404, {"error": "not-found"})

    do_POST = _mutation
    do_PUT = _mutation
    do_PATCH = _mutation
    do_DELETE = _mutation


class _Server:
    def __init__(self):
        self.state = _State()
        handler = type("FixtureHandler", (_Handler,), {"state": self.state})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def origin(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def _grant(*, tool, target, method, key):
    now = datetime.now(timezone.utc)
    effect = "REMOTE_MUTATION_HIGH_IMPACT"
    authority = {
        "approval": {
            "approved": True,
            "approved_by": "fixture-operator",
            "approval_id": f"approval-{key}",
            "tool": tool,
            "scope": "global-working-memory",
            "effect_class": effect,
            "target_url": target,
            "method": method,
            "idempotency_key": key,
            "one_shot": True,
            "high_impact_ack": True,
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }
    }
    return build_mutation_grant(
        request_id=f"request-{key}",
        tool=tool,
        scope="global-working-memory",
        effect_class=effect,
        payload={"url": target, "method": method, "idempotency_key": key},
        authority_context=authority,
        now=now,
    )


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_exact_http_mutation_with_fresh_readback(tmp_path, method):
    with _Server() as server:
        url = server.origin + "/mutate"
        payload = {
            "url": url,
            "method": method,
            "idempotency_key": f"idem-{method.lower()}",
            "json": {"value": 1},
            "precheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"value": 0},
            },
            "postcheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"value": 1},
            },
            "expected_status": 200,
            "timeout_seconds": 10,
        }
        payload["_aios_mutation_grant"] = _grant(
            tool="browser.mutate.request",
            target=url,
            method=method,
            key=payload["idempotency_key"],
        )
        result = asyncio.run(
            mutate_request_async(
                payload,
                allow_private_fixture=True,
                ledger=MutationLedger(tmp_path / f"{method}.sqlite3"),
            )
        )
        assert result["terminal_status"] == "SUCCEEDED"
        assert result["semantic_success"] is True
        assert server.state.value == 1


def _artifact(tmp_path, body=b"upload-fixture"):
    root = tmp_path / "artifacts"
    root.mkdir()
    path = root / "fixture.txt"
    path.write_bytes(body)
    ref = ArtifactRef("artifact:test:live-upload")
    descriptor = ArtifactDescriptor(
        ref=ref,
        runtime_path=path,
        expected_sha256="sha256:" + sha256(body).hexdigest(),
        media_type="text/plain",
        display_name="fixture.txt",
    )
    return root, ref, SyntheticArtifactResolver({ref.value: descriptor})


def test_live_upload_auto_submit_is_gated_and_verified(tmp_path):
    with _Server() as server:
        root, ref, resolver = _artifact(tmp_path)
        mutation_url = server.origin + "/upload-target"
        key = "idem-upload-one"
        payload = {
            "page_url": server.origin + "/upload",
            "mutation_url": mutation_url,
            "method": "POST",
            "idempotency_key": key,
            "artifact_ref": ref.value,
            "file_locator": {"strategy": "label", "value": "Fixture file"},
            "postcheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"uploads": 1},
            },
            "expected_status": 201,
            "timeout_seconds": 10,
            "_aios_mutation_grant": _grant(
                tool="browser.upload.execute",
                target=mutation_url,
                method="POST",
                key=key,
            ),
        }
        result = asyncio.run(
            upload_execute_async(
                payload,
                allow_private_fixture=True,
                ledger=MutationLedger(tmp_path / "upload.sqlite3"),
                artifact_resolver=resolver,
                artifact_root=root,
            )
        )
        assert result["terminal_status"] == "SUCCEEDED"
        assert result["mutation_count"] == 1
        assert server.state.uploads == 1
        assert server.state.extra_mutations == 0


def test_live_upload_second_mutation_is_blocked(tmp_path):
    with _Server() as server:
        root, ref, resolver = _artifact(tmp_path)
        mutation_url = server.origin + "/upload-target"
        key = "idem-upload-double"
        payload = {
            "page_url": server.origin + "/upload-double",
            "mutation_url": mutation_url,
            "method": "POST",
            "idempotency_key": key,
            "artifact_ref": ref.value,
            "file_locator": {"strategy": "label", "value": "Fixture file"},
            "postcheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"uploads": 1},
            },
            "expected_status": 201,
            "timeout_seconds": 10,
            "_aios_mutation_grant": _grant(
                tool="browser.upload.execute",
                target=mutation_url,
                method="POST",
                key=key,
            ),
        }
        result = asyncio.run(
            upload_execute_async(
                payload,
                allow_private_fixture=True,
                ledger=MutationLedger(tmp_path / "upload-double.sqlite3"),
                artifact_resolver=resolver,
                artifact_root=root,
            )
        )
        assert result["terminal_status"] == "MUTATION_STATE_UNKNOWN"
        assert server.state.uploads == 1
        assert server.state.extra_mutations == 0


def test_reversible_mutation_rolls_back_and_verifies(tmp_path):
    with _Server() as server:
        url = server.origin + "/mutate"
        rollback = {
            "url": server.origin + "/rollback",
            "method": "POST",
            "json": {"restore": 0},
            "expected_status": 200,
            "postcheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"value": 0},
            },
        }
        now = datetime.now(timezone.utc)
        key = "idem-reversible"
        effect = "REMOTE_MUTATION_REVERSIBLE"
        authority = {
            "approval": {
                "approved": True,
                "approved_by": "fixture-operator",
                "approval_id": "approval-reversible",
                "tool": "browser.mutate.reversible",
                "scope": "global-working-memory",
                "effect_class": effect,
                "target_url": url,
                "method": "POST",
                "idempotency_key": key,
                "one_shot": True,
                "rollback_fingerprint": mutation_contract_fingerprint(rollback),
                "expires_at": (now + timedelta(minutes=5)).isoformat(),
            }
        }
        payload = {
            "url": url,
            "method": "POST",
            "idempotency_key": key,
            "json": {"value": 1},
            "precheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"value": 0},
            },
            "postcheck": {
                "url": server.origin + "/state",
                "expected_status": 200,
                "expected_json_subset": {"value": 1},
            },
            "expected_status": 200,
            "timeout_seconds": 10,
            "rollback": rollback,
        }
        payload["_aios_mutation_grant"] = build_mutation_grant(
            request_id="request-reversible",
            tool="browser.mutate.reversible",
            scope="global-working-memory",
            effect_class=effect,
            payload=payload,
            authority_context=authority,
            now=now,
        )
        ledger = MutationLedger(tmp_path / "reversible.sqlite3")
        result = asyncio.run(
            mutate_reversible_async(
                payload,
                allow_private_fixture=True,
                ledger=ledger,
            )
        )
        assert result["terminal_status"] == "ROLLED_BACK"
        assert result["rollback_verified"] is True
        assert server.state.value == 0
        assert ledger.status(key) == "ROLLED_BACK"
