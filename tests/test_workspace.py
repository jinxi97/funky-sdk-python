from __future__ import annotations

import pytest

from funky import ExecutionResult, Workspace


def test_workspace_create_returns_workspace_instance() -> None:
    ws = Workspace.create()
    assert isinstance(ws, Workspace)


def test_execute_returns_structured_result() -> None:
    ws = Workspace.create()
    result = ws.execute("echo hi")

    assert isinstance(result, ExecutionResult)
    assert hasattr(result, "stdout")
    assert hasattr(result, "stderr")
    assert hasattr(result, "exit_code")


def test_execute_fixed_fake_output() -> None:
    ws = Workspace.create()
    result = ws.execute("anything")

    assert result.stdout == "Command executed!"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_execute_ok_true_for_zero_exit_code() -> None:
    ws = Workspace.create()
    result = ws.execute("ls")

    assert result.ok is True


def test_import_from_funky() -> None:
    from funky import Workspace as ImportedWorkspace

    assert ImportedWorkspace is Workspace


def test_execute_allows_empty_command() -> None:
    ws = Workspace.create()
    result = ws.execute("")

    assert result.stdout == "Command executed!"
    assert result.stderr == ""
    assert result.exit_code == 0


@pytest.mark.parametrize("bad_command", [None, 123, 1.2, object(), ["echo hi"]])
def test_execute_raises_type_error_for_non_string_command(bad_command: object) -> None:
    ws = Workspace.create()
    with pytest.raises(TypeError):
        ws.execute(bad_command)  # type: ignore[arg-type]
