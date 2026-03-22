from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import socket
from urllib.error import HTTPError, URLError

import pytest

import funky
import funky._http
from funky import APIError, ExecutionResult, Workspace


@dataclass
class FakeResponse:
    body: bytes

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@dataclass
class FakeSSEResponse:
    """Fake response that yields lines for SSE streaming."""
    lines: list[bytes] = field(default_factory=list)

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        pass


def make_ready_sse_lines(
    claim_name: str = "workspace-claim-abc",
    pod_name: str = "pod-123",
) -> list[bytes]:
    """Build raw SSE lines for a successful ready event."""
    return [
        b"event: status\n",
        b'data: {"status": "creating", "claim_name": "' + claim_name.encode() + b'"}\n',
        b"\n",
        b"event: status\n",
        b'data: {"status": "ready", "sandbox": {"sandbox_name": "sb-1", "pod_name": "' + pod_name.encode() + b'"}}\n',
        b"\n",
    ]


def fake_urlopen_for_create(
    claim_name: str = "workspace-claim-abc",
    namespace: str = "test-ns",
    pod_name: str = "pod-123",
):
    """Return a fake_urlopen that handles the two-step create flow."""
    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/workspace") and request.get_method() == "POST":
            body = (
                b'{"claim_name": "' + claim_name.encode()
                + b'", "status": "creating", "namespace": "' + namespace.encode()
                + b'", "template_name": "tpl"}'
            )
            return FakeResponse(body=body)
        if "/workspace/" in request.full_url and "/events" in request.full_url:
            return FakeSSEResponse(lines=make_ready_sse_lines(claim_name, pod_name))
        # Fallback for other endpoints (execute, delete, etc.)
        return FakeResponse(body=b'{}')

    return fake_urlopen


# --- Creation tests ---


def test_workspace_create_returns_workspace_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen_for_create())
    ws = Workspace.create()

    assert isinstance(ws, Workspace)
    assert ws.claim_name == "workspace-claim-abc"
    assert ws.namespace == "test-ns"
    assert ws.pod_name == "pod-123"


def test_workspace_create_stores_claim_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen_for_create(claim_name="my-claim"))
    ws = Workspace.create()

    assert ws.claim_name == "my-claim"


def test_workspace_create_raises_on_failed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/workspace") and request.get_method() == "POST":
            return FakeResponse(body=b'{"claim_name": "c1", "status": "creating", "namespace": "ns"}')
        return FakeSSEResponse(lines=[
            b"event: status\n",
            b'data: {"status": "failed", "detail": "out of resources"}\n',
            b"\n",
        ])

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    with pytest.raises(APIError) as exc_info:
        Workspace.create()

    assert "out of resources" in str(exc_info.value)


def test_workspace_create_raises_when_stream_ends_without_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/workspace") and request.get_method() == "POST":
            return FakeResponse(body=b'{"claim_name": "c1", "status": "creating", "namespace": "ns"}')
        # SSE stream with only a creating event, then closes
        return FakeSSEResponse(lines=[
            b"event: status\n",
            b'data: {"status": "creating"}\n',
            b"\n",
        ])

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    with pytest.raises(APIError) as exc_info:
        Workspace.create()

    assert "without workspace becoming ready" in str(exc_info.value)


def test_workspace_create_raises_on_unexpected_create_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        return FakeResponse(body=b'"just-a-string"')

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    with pytest.raises(APIError) as exc_info:
        Workspace.create()

    assert "expected object with claim_name" in str(exc_info.value)


def test_workspace_create_timeout_has_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout: float):
        raise URLError(socket.timeout("timed out"))

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    with pytest.raises(APIError) as exc_info:
        Workspace.create(timeout=5.0)

    assert exc_info.value.status_code == 0
    assert "timed out" in str(exc_info.value).lower()


# --- Execution tests ---


def test_execute_returns_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list = []
    base_fake = fake_urlopen_for_create()

    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/execute") and request.get_method() == "POST":
            captured.append(request)
            return FakeResponse(b'{"stdout":"remote-output","stderr":"warn","exit_code":3}')
        return base_fake(request, timeout)

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create()
    result = ws.execute("echo hi")

    assert isinstance(result, ExecutionResult)
    assert result.stdout == "remote-output"
    assert result.stderr == "warn"
    assert result.exit_code == 3
    assert result.ok is False
    # Verify JSON body was sent
    import json
    body = json.loads(captured[0].data)
    assert body["command"] == "echo hi"
    assert body["claim_name"] == "workspace-claim-abc"
    assert body["pod_name"] == "pod-123"


def test_execute_raises_type_error_for_non_string_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen_for_create())
    ws = Workspace.create()

    with pytest.raises(TypeError):
        ws.execute(123)  # type: ignore[arg-type]


def test_execute_allows_empty_command(monkeypatch: pytest.MonkeyPatch) -> None:
    base_fake = fake_urlopen_for_create()

    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/execute") and request.get_method() == "POST":
            return FakeResponse(b'{"stdout":"done","stderr":"","exit_code":0}')
        return base_fake(request, timeout)

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create()
    result = ws.execute("")

    assert result.stdout == "done"
    assert result.exit_code == 0


def test_api_error_maps_validation_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        raise HTTPError(
            url=request.full_url,
            code=422,
            msg="Unprocessable Entity",
            hdrs=None,
            fp=BytesIO(
                b'{"detail":[{"loc":["query","command"],"msg":"field required","type":"value_error.missing"}]}'
            ),
        )

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    with pytest.raises(APIError) as exc_info:
        Workspace.create()

    assert exc_info.value.status_code == 422
    assert "field required" in str(exc_info.value)


# --- Import test ---


def test_import_from_funky() -> None:
    from funky import Workspace as ImportedWorkspace

    assert ImportedWorkspace is Workspace


# --- Delete tests ---


def test_delete_calls_workspace_delete_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    requests_made: list = []
    base_fake = fake_urlopen_for_create(claim_name="ws-delete-id", namespace="test-ns")

    def fake_urlopen(request, timeout: float):
        requests_made.append(request)
        if request.get_method() == "DELETE":
            return FakeResponse(b'{"deleted": true}')
        return base_fake(request, timeout)

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create()
    result = ws.delete()

    assert result == {"deleted": True}
    delete_req = [r for r in requests_made if r.get_method() == "DELETE"]
    assert len(delete_req) == 1
    assert "/workspace/ws-delete-id" in delete_req[0].full_url
    assert "namespace=test-ns" in delete_req[0].full_url


def test_delete_raises_on_unexpected_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_fake = fake_urlopen_for_create(claim_name="ws-delete-id")

    def fake_urlopen(request, timeout: float):
        if request.get_method() == "DELETE":
            return FakeResponse(b'{"ok": true}')
        return base_fake(request, timeout)

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create()

    with pytest.raises(APIError) as exc_info:
        ws.delete()

    assert exc_info.value.status_code == 200
