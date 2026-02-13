"""Public fake Funky SDK API."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result returned by Workspace.execute."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        """Whether command execution succeeded."""
        return self.exit_code == 0


class Workspace:
    """Fake workspace client used for local demos and integration tests."""

    @classmethod
    def create(cls) -> Workspace:
        """Create a fake workspace client."""
        return cls()

    def execute(self, command: str) -> ExecutionResult:
        """
        Execute a command in the fake workspace.

        The fake implementation is deterministic and does not run shell code.
        """
        if not isinstance(command, str):
            raise TypeError("command must be a string")

        return ExecutionResult(
            stdout="Command executed!",
            stderr="",
            exit_code=0,
        )


__all__ = ["ExecutionResult", "Workspace"]
