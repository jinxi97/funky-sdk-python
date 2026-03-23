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
            url=f"{normalized_url}/workspaces",
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
            url=f"{normalized_url}/workspaces/{claim_name}/events?namespace={namespace}",
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
        execution_response = post_and_parse_json(
            url=f"{self._base_url}/workspaces/{quote(self.claim_name, safe='')}/execute",
            body={
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

    def snapshot(self) -> Workspace:
        """Take a snapshot of this workspace. Blocks until the snapshot is ready."""
        # Step 1: Create the snapshot trigger.
        trigger_response = post_and_parse_json(
            url=f"{self._base_url}/snapshots/triggers",
            body={
                "claim_name": self.claim_name,
                "namespace": self.namespace,
                "pod_name": self.pod_name,
            },
            timeout=self._timeout,
        )
        if not isinstance(trigger_response, dict) or not isinstance(trigger_response.get("name"), str):
            raise APIError(
                status_code=200,
                message="Unexpected response format: expected object with trigger name",
                details=trigger_response,
            )
        trigger_name: str = trigger_response["name"]

        # Step 2: Wait for the snapshot to become ready via SSE.
        for _event_type, data in stream_sse(
            url=(
                f"{self._base_url}/snapshots/triggers/{quote(trigger_name, safe='')}/events"
                f"?namespace={quote(self.namespace, safe='')}"
            ),
            timeout=self._timeout,
        ):
            if not isinstance(data, dict):
                continue
            status = data.get("status")
            if status == "ready":
                return self
            if status == "failed":
                raise APIError(
                    status_code=500,
                    message=f"Snapshot failed: {data.get('detail', 'unknown error')}",
                    details=data,
                )

        raise APIError(
            status_code=0,
            message="SSE stream ended without snapshot becoming ready",
        )

    @classmethod
    def restore(
        cls,
        claim_name: str,
        namespace: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Workspace:
        """Restore a new workspace from the latest snapshot of the given workspace.

        Blocks until the restored workspace is ready.
        """
        normalized_url = base_url.rstrip("/")

        # Step 1: Request the restore.
        restore_response = post_and_parse_json(
            url=f"{normalized_url}/snapshots/restore",
            body={"claim_name": claim_name, "namespace": namespace},
            timeout=timeout,
        )
        if not isinstance(restore_response, dict) or not isinstance(restore_response.get("claim_name"), str):
            raise APIError(
                status_code=200,
                message="Unexpected response format: expected object with claim_name",
                details=restore_response,
            )
        restored_claim: str = restore_response["claim_name"]
        namespace: str = restore_response.get("namespace", "")

        # Step 2: Wait for the restored workspace to become ready via SSE.
        pod_name = ""
        for _event_type, data in stream_sse(
            url=f"{normalized_url}/snapshots/restore/{restored_claim}/events?namespace={namespace}",
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
                    message=f"Restore failed: {data.get('detail', 'unknown error')}",
                    details=data,
                )

        if not pod_name:
            raise APIError(
                status_code=0,
                message="SSE stream ended without restored workspace becoming ready",
            )

        return cls(
            claim_name=restored_claim,
            namespace=namespace,
            pod_name=pod_name,
            base_url=base_url,
            timeout=timeout,
        )

    def delete(self) -> dict:
        """Delete this workspace."""
        delete_response = delete_and_parse_json(
            url=(
                f"{self._base_url}/workspaces/{quote(self.claim_name, safe='')}"
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
