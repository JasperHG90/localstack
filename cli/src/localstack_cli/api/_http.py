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
        # Nomad answers 403 for both a dead token and a policy gap. The body
        # is what separates them: it names the missing capability only in the
        # second case.
        body = response.text.lower()
        if "acl token not found" in body or "token expired" in body or "not found" in body:
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
