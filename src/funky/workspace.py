"""Workspace client implementation."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from ._http import delete_and_parse_json, post_and_parse_json, stream_sse
from .constants import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS
from .errors import APIError
from .models import ExecutionResult


class Workspace:
    """Workspace client that calls the Funky backend API."""

    def __init__(
        self,
        claim_name: str,
        namespace: str,
        pod_name: str,
        base_url: str,
        timeout: float,
    ) -> None:
        self.claim_name = claim_name
        self.namespace = namespace
        self.pod_name = pod_name
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @classmethod
    def create(
        cls,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Workspace:
        """
        Create a new workspace through the Funky API.

        Blocks until the workspace is ready by consuming the SSE event stream.
        """
        normalized_url = base_url.rstrip("/")

        # Step 1: Create the workspace claim.
        create_response = post_and_parse_json(
            url=f"{normalized_url}/workspace",
            timeout=timeout,
        )
        if not isinstance(create_response, dict) or not isinstance(create_response.get("claim_name"), str):
            raise APIError(
                status_code=200,
                message="Unexpected response format: expected object with claim_name",
                details=create_response,
            )
        claim_name: str = create_response["claim_name"]
        namespace: str = create_response.get("namespace", "")

        # Step 2: Wait for the workspace to become ready via SSE.
        pod_name = ""
        for _event_type, data in stream_sse(
            url=f"{normalized_url}/workspace/{claim_name}/events?namespace={namespace}",
            timeout=timeout,
        ):
            if not isinstance(data, dict):
                continue
            status = data.get("status")
            if status == "ready":
                sandbox = data.get("sandbox", {})
                pod_name = sandbox.get("pod_name", "")
                break
            if status == "failed":
                raise APIError(
                    status_code=500,
                    message=f"Workspace creation failed: {data.get('detail', 'unknown error')}",
                    details=data,
                )

        if not pod_name:
            raise APIError(
                status_code=0,
                message="SSE stream ended without workspace becoming ready",
            )

        return cls(
            claim_name=claim_name,
            namespace=namespace,
            pod_name=pod_name,
            base_url=base_url,
            timeout=timeout,
        )

    def execute(self, command: str) -> ExecutionResult:
        """Execute a command in this workspace."""
        if not isinstance(command, str):
            raise TypeError("command must be a string")

        execution_response = post_and_parse_json(
            url=f"{self._base_url}/execute",
            body={
                "claim_name": self.claim_name,
                "namespace": self.namespace,
                "pod_name": self.pod_name,
                "command": command,
            },
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

    def delete(self) -> dict:
        """Delete this workspace."""
        delete_response = delete_and_parse_json(
            url=(
                f"{self._base_url}/workspace/{quote(self.claim_name, safe='')}"
                f"?{urlencode({'namespace': self.namespace})}"
            ),
            timeout=self._timeout,
        )
        if isinstance(delete_response, dict) and delete_response.get("deleted"):
            return delete_response

        raise APIError(
            status_code=200,
            message=(
                "Unexpected response format from Funky API: "
                "expected {\"deleted\": true}"
            ),
            details=delete_response,
        )
