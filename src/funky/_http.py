"""Internal HTTP helpers."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import APIError


def post_and_parse_json(url: str, api_secret: str, timeout: float) -> Any:
    payload = b"{}"
    request = Request(
        url=url,
        data=payload,
        method="POST",
        headers={
            "x-api-secret": api_secret,
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        error_details = safe_parse_json(exc.read())
        raise APIError(
            status_code=exc.code,
            message=extract_error_message(error_details) or exc.reason or "API request failed",
            details=error_details,
        ) from exc
    except URLError as exc:
        raise APIError(status_code=0, message=f"Network error: {exc.reason}") from exc

    return safe_parse_json(body)


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
