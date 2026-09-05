"""Minimal HTTP GET helper for the backend's own Nomad/Consul calls.

Copied down from `cli/src/localstack_cli/api/_http.py`, simplified. The
original carries a 401-vs-403 typed-error taxonomy
(`localstack_cli.api.errors`) so cli's interactive command layer can tell a
dead token from a missing capability and prompt the human to re-login. This
app has no login flow to prompt through: `main.py`'s `/api/status` handler
already turns any fetch failure into an "unknown" tile plus a plain error
string, so that distinction is not load-bearing here. One exception type is
enough.
"""

from typing import Any

import httpx

TIMEOUT_SECONDS = 2.0


class FetchError(Exception):
    """Any failure fetching or parsing a URL: network, timeout, or a
    non-2xx/non-JSON response."""


def get_json(
    url: str,
    token: str | None = None,
    token_header: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> tuple[Any, httpx.Headers]:
    """GET `url` and return its parsed body plus response headers.

    Response headers are returned alongside the body because
    `nomad_client.job_statuses` reads pagination state
    (`X-Nomad-Nexttoken`) off them.
    """
    headers = {}
    if token and token_header:
        headers[token_header] = token

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
            response = client.get(url, headers=headers)
    except httpx.HTTPError as error:
        raise FetchError(f"{url}: {error}") from error

    if response.status_code >= 400:
        raise FetchError(f"{url} returned {response.status_code}")

    try:
        return response.json(), response.headers
    except ValueError as error:
        raise FetchError(f"{url} did not return JSON") from error
