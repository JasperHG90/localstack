"""One place that turns an HTTP outcome into one of `errors`' states.

Split out because three fetchers classify the same failures, and three
copies would drift. The 401-vs-403 split is the whole point: see
`errors.NotAuthenticated` against `errors.MissingCapability`.
"""

from typing import Any

import httpx

from localstack_cli.api.errors import (
    MissingCapability,
    NotAuthenticated,
    NotFound,
    Timeout,
    Unreachable,
)

# Two seconds. Long enough for a home cluster over the edge, short enough
# that a dead source degrades its panel inside one refresh interval.
TIMEOUT_SECONDS = 2.0


def get_json(
    service: str,
    url: str,
    capability: str,
    token: str | None = None,
    token_header: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> tuple[Any, httpx.Headers]:
    """GET `url` and return its parsed body plus response headers.

    `capability` names the grant this call needs, so a 403 can say which one
    is missing rather than rendering an empty table.
    """
    headers = {}
    if token and token_header:
        headers[token_header] = token

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as error:
        raise Timeout(service, f"{timeout}s") from error
    except httpx.HTTPError as error:
        raise Unreachable(service, url) from error

    if response.status_code == 401:
        raise NotAuthenticated(service)
    if response.status_code == 403:
        # Both a dead token and a policy gap answer 403, and the body is the
        # only hint at this layer. Measured against the live cluster:
        # Vault sends "permission denied ... invalid token" for a bad token,
        # Nomad sends "ACL token not found".
        #
        # This is a hint, not the verdict. Sniffing a body is brittle, so the
        # command layer re-asks the service directly before it tells anyone
        # to log in. See `commands/_session.py`.
        body = response.text.lower()
        dead = ("acl token not found", "token expired", "invalid token", "token not found")
        if any(marker in body for marker in dead):
            raise NotAuthenticated(service)
        raise MissingCapability(service, capability)
    if response.status_code == 404:
        raise NotFound(service, url)
    if response.status_code >= 400:
        raise Unreachable(service, f"{url} returned {response.status_code}")

    try:
        return response.json(), response.headers
    except ValueError as error:
        raise Unreachable(service, f"{url} did not return JSON") from error
