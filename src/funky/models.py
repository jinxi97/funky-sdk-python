"""Data models for funky SDK."""

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
