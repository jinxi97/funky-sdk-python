"""Internal HTTP helpers."""

from __future__ import annotations

import json
import socket
import ssl
from collections.abc import Generator
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from .errors import APIError


@lru_cache(maxsize=1)
def _default_ssl_context() -> ssl.SSLContext:
    """Build a stable CA-backed SSL context for outbound HTTPS requests."""
    return ssl.create_default_context(cafile=certifi.where())


def _urlopen(request: Request, timeout: float):
    return urlopen(request, timeout=timeout, context=_default_ssl_context())


def post_and_parse_json(
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    """POST to *url* and return the parsed JSON response.

    If *body* is provided it is sent as ``application/json``;
    otherwise an empty payload is sent (matching the old behaviour).
    """
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        content_type = "application/json"
    else:
        payload = b""
        content_type = "application/x-www-form-urlencoded"
    headers: dict[str, str] = {
        "accept": "application/json",
        "content-type": content_type,
    }
    request = Request(
        url=url,
        data=payload,
        method="POST",
        headers=headers,
    )
    try:
        with _urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        error_details = safe_parse_json(exc.read())
        raise APIError(
            status_code=exc.code,
            message=extract_error_message(error_details) or exc.reason or "API request failed",
            details=error_details,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError | socket.timeout):
            raise APIError(
                status_code=0,
                message=(
                    f"Request timed out after {timeout:.1f}s while calling {url}. "
                    "Try increasing the timeout in Workspace.create(timeout=...)."
                ),
            ) from exc
        raise APIError(status_code=0, message=f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise APIError(
            status_code=0,
            message=(
                f"Request timed out after {timeout:.1f}s while calling {url}. "
                "Try increasing the timeout in Workspace.create(timeout=...)."
            ),
        ) from exc
    except socket.timeout as exc:
        raise APIError(
            status_code=0,
            message=(
                f"Request timed out after {timeout:.1f}s while calling {url}. "
                "Try increasing the timeout in Workspace.create(timeout=...)."
            ),
        ) from exc

    return safe_parse_json(body)


def get_and_parse_json(url: str, timeout: float) -> Any:
    """GET from *url* and return the parsed JSON response."""
    request = Request(
        url=url,
        method="GET",
        headers={"accept": "application/json"},
    )
    try:
        with _urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        error_details = safe_parse_json(exc.read())
        raise APIError(
            status_code=exc.code,
            message=extract_error_message(error_details) or exc.reason or "API request failed",
            details=error_details,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError | socket.timeout):
            raise APIError(
                status_code=0,
                message=f"Request timed out after {timeout:.1f}s while calling {url}.",
            ) from exc
        raise APIError(status_code=0, message=f"Network error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise APIError(
            status_code=0,
            message=f"Request timed out after {timeout:.1f}s while calling {url}.",
        ) from exc

    return safe_parse_json(body)


def delete_and_parse_json(url: str, timeout: float) -> Any:
    request = Request(
        url=url,
        method="DELETE",
        headers={"accept": "application/json"},
    )
    try:
        with _urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        error_details = safe_parse_json(exc.read())
        raise APIError(
            status_code=exc.code,
            message=extract_error_message(error_details) or exc.reason or "API request failed",
            details=error_details,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError | socket.timeout):
            raise APIError(
                status_code=0,
                message=(
                    f"Request timed out after {timeout:.1f}s while calling {url}. "
                    "Try increasing the timeout in Workspace.create(timeout=...)."
                ),
            ) from exc
        raise APIError(status_code=0, message=f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise APIError(
            status_code=0,
            message=(
                f"Request timed out after {timeout:.1f}s while calling {url}. "
                "Try increasing the timeout in Workspace.create(timeout=...)."
            ),
        ) from exc
    except socket.timeout as exc:
        raise APIError(
            status_code=0,
            message=(
                f"Request timed out after {timeout:.1f}s while calling {url}. "
                "Try increasing the timeout in Workspace.create(timeout=...)."
            ),
        ) from exc

    return safe_parse_json(body)


def stream_sse(url: str, timeout: float) -> Generator[tuple[str, Any], None, None]:
    """Open a GET request to an SSE endpoint and yield (event_type, parsed_data) tuples."""
    request = Request(
        url=url,
        method="GET",
        headers={"accept": "text/event-stream"},
    )
    try:
        response = _urlopen(request, timeout=timeout)
    except HTTPError as exc:
        error_details = safe_parse_json(exc.read())
        raise APIError(
            status_code=exc.code,
            message=extract_error_message(error_details) or exc.reason or "SSE request failed",
            details=error_details,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError | socket.timeout):
            raise APIError(
                status_code=0,
                message=f"SSE connection timed out after {timeout:.1f}s while calling {url}.",
            ) from exc
        raise APIError(status_code=0, message=f"Network error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise APIError(
            status_code=0,
            message=f"SSE connection timed out after {timeout:.1f}s while calling {url}.",
        ) from exc

    try:
        event_type = ""
        data_buf = ""
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf += line[len("data:"):].strip()
            elif line == "":
                # Empty line = end of event
                if data_buf:
                    parsed = safe_parse_json(data_buf.encode("utf-8"))
                    yield (event_type or "message", parsed)
                event_type = ""
                data_buf = ""
    finally:
        response.close()


def safe_parse_json(data: bytes) -> Any:
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def extract_error_message(details: Any) -> str | None:
    if isinstance(details, dict):
        detail_value = details.get("detail")
        if isinstance(detail_value, str):
            return detail_value
        if isinstance(detail_value, list) and detail_value:
            first = detail_value[0]
            if isinstance(first, dict):
                message = first.get("msg")
                if isinstance(message, str):
                    return message
    return None
