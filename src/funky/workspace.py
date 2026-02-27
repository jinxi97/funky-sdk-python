"""Workspace client implementation."""

from __future__ import annotations

import os
from urllib.parse import quote, urlencode

from ._http import delete_and_parse_json, post_and_parse_json
from .constants import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS
from .errors import APIError, ConfigurationError
from .models import ExecutionResult


class Workspace:
    """Workspace client that calls the Funky backend API."""

    def __init__(self, workspace_id: str, api_secret: str, base_url: str, timeout: float) -> None:
        self.workspace_id = workspace_id
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @classmethod
    def create(
        cls,
        api_secret: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Workspace:
        """
        Create a new workspace through the Funky API.

        If api_secret is not provided, the SDK reads FUNKY_API_SECRET.
        """
        resolved_secret = api_secret or os.getenv("FUNKY_API_SECRET")
        if not resolved_secret:
            raise ConfigurationError("Missing API secret. Set FUNKY_API_SECRET or pass api_secret.")

        workspace_id_response = post_and_parse_json(
            url=f"{base_url.rstrip('/')}/workspaces",
            api_secret=resolved_secret,
            timeout=timeout,
        )
        if isinstance(workspace_id_response, str):
            workspace_id = workspace_id_response
        elif isinstance(workspace_id_response, dict) and isinstance(workspace_id_response.get("workspace_id"), str):
            workspace_id = workspace_id_response["workspace_id"]
        else:
            raise APIError(
                status_code=200,
                message="Unexpected response format from Funky API: expected workspace id string",
                details=workspace_id_response,
            )
        return cls(
            workspace_id=workspace_id,
            api_secret=resolved_secret,
            base_url=base_url,
            timeout=timeout,
        )

    def execute(self, command: str) -> ExecutionResult:
        """Execute a command in this workspace."""
        if not isinstance(command, str):
            raise TypeError("command must be a string")

        execution_response = post_and_parse_json(
            url=(
                f"{self._base_url}/workspaces/{quote(self.workspace_id, safe='')}/exec"
                f"?{urlencode({'command': command})}"
            ),
            api_secret=self._api_secret,
            timeout=self._timeout,
        )
        if (
            isinstance(execution_response, dict)
            and isinstance(execution_response.get("stdout"), str)
            and isinstance(execution_response.get("stderr"), str)
            and isinstance(execution_response.get("exit_code"), int)
        ):
            return ExecutionResult(
                stdout=execution_response["stdout"],
                stderr=execution_response["stderr"],
                exit_code=execution_response["exit_code"],
            )

        raise APIError(
            status_code=200,
            message=(
                "Unexpected response format from Funky API: "
                "expected object with stdout/stderr/exit_code"
            ),
            details=execution_response,
        )

    def delete(self) -> str:
        """Delete this workspace."""
        delete_response = delete_and_parse_json(
            url=f"{self._base_url}/workspaces/{quote(self.workspace_id, safe='')}",
            api_secret=self._api_secret,
            timeout=self._timeout,
        )
        if isinstance(delete_response, str):
            return delete_response

        raise APIError(
            status_code=200,
            message=(
                "Unexpected response format from Funky API: "
                "expected delete response string"
            ),
            details=delete_response,
        )
