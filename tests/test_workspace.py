from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from urllib.error import HTTPError

import pytest

import funky
import funky._http
from funky import APIError, ConfigurationError, ExecutionResult, Workspace


@dataclass
class FakeResponse:
    body: bytes

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_workspace_create_returns_workspace_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fake_urlopen(request, timeout: float):
        calls.append((request, timeout))
        return FakeResponse(b'"workspace-123"')

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create(api_secret="test-secret")

    assert isinstance(ws, Workspace)
    assert ws.workspace_id == "workspace-123"
    assert len(calls) == 1


def test_workspace_create_reads_secret_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout: float):
        assert request.headers["X-api-secret"] == "env-secret"
        return FakeResponse(b'"workspace-abc"')

    monkeypatch.setenv("FUNKY_API_SECRET", "env-secret")
    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)

    ws = Workspace.create()
    assert ws.workspace_id == "workspace-abc"


def test_workspace_create_raises_without_api_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FUNKY_API_SECRET", raising=False)

    with pytest.raises(ConfigurationError):
        Workspace.create()


def test_execute_returns_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_urlopen(request, timeout: float):
        urls.append(request.full_url)
        if request.full_url.endswith("/workspaces"):
            return FakeResponse(b'"ws-id"')
        return FakeResponse(b'{"stdout":"remote-output","stderr":"warn","exit_code":3}')

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create(api_secret="secret")
    result = ws.execute("echo hi")

    assert isinstance(result, ExecutionResult)
    assert result.stdout == "remote-output"
    assert result.stderr == "warn"
    assert result.exit_code == 3
    assert result.ok is False
    assert "/workspaces/ws-id/exec?command=echo+hi" in urls[1]


def test_execute_raises_type_error_for_non_string_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout: float):
        return FakeResponse(b'"workspace-123"')

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create(api_secret="secret")

    with pytest.raises(TypeError):
        ws.execute(123)  # type: ignore[arg-type]


def test_execute_allows_empty_command(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_urlopen(request, timeout: float):
        urls.append(request.full_url)
        if request.full_url.endswith("/workspaces"):
            return FakeResponse(b'"ws-id"')
        return FakeResponse(b'{"stdout":"done","stderr":"","exit_code":0}')

    monkeypatch.setattr(funky._http, "urlopen", fake_urlopen)
    ws = Workspace.create(api_secret="secret")
    result = ws.execute("")

    assert result.stdout == "done"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert "command=" in urls[1]


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
        Workspace.create(api_secret="secret")

    assert exc_info.value.status_code == 422
    assert "field required" in str(exc_info.value)


def test_import_from_funky() -> None:
    from funky import Workspace as ImportedWorkspace

    assert ImportedWorkspace is Workspace
