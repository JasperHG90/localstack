"""`_http.get_json`, against respx -- no real network.

Modeled on `cli/tests/test_api_nomad.py`'s own respx convention (this
project's own `_http.py` is a simplified copy, so its tests cover the same
shape minus the dropped typed-error taxonomy: token-header placement and
non-2xx/non-JSON failures collapse to one `FetchError`).
"""

import httpx
import respx

from dash_app._http import FetchError, get_json

URL = "https://example.test.invalid/v1/thing"


@respx.mock
def test_a_successful_response_returns_body_and_headers() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))

    body, headers = get_json(URL)

    assert body == {"ok": True}
    assert headers is not None


@respx.mock
def test_the_token_is_sent_under_the_given_header() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={}))

    get_json(URL, token="a-token", token_header="X-Nomad-Token")

    assert route.calls.last.request.headers["X-Nomad-Token"] == "a-token"


@respx.mock
def test_no_token_header_is_sent_without_a_token() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={}))

    get_json(URL)

    assert "X-Nomad-Token" not in route.calls.last.request.headers


@respx.mock
def test_a_non_2xx_response_raises_fetch_error() -> None:
    respx.get(URL).mock(return_value=httpx.Response(403, text="denied"))

    try:
        get_json(URL)
    except FetchError as error:
        assert "403" in str(error)
    else:
        raise AssertionError("expected FetchError")


@respx.mock
def test_a_non_json_response_raises_fetch_error() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="not json"))

    try:
        get_json(URL)
    except FetchError as error:
        assert "did not return JSON" in str(error)
    else:
        raise AssertionError("expected FetchError")


@respx.mock
def test_a_refused_connection_raises_fetch_error() -> None:
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))

    try:
        get_json(URL)
    except FetchError as error:
        assert URL in str(error)
    else:
        raise AssertionError("expected FetchError")
