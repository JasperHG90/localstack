"""The async I/O layer, respx-mocked.

Async helpers are driven with `asyncio.run(...)` from sync test functions,
the same shape `test_http.py` uses, so no pytest-asyncio is needed.
"""

from __future__ import annotations

import asyncio
import io
import tarfile
from collections.abc import AsyncIterator, Callable, Iterator

import httpx
import pytest
import respx

from registry_ui._http import FetchError
from registry_ui.registry_client import MAX_BLOB_BYTES, MAX_CONNECTIONS, RegistryClient

REG = "https://registry.example.test"


class _Stream(httpx.AsyncByteStream):
    """A response body the test can watch being consumed."""

    def __init__(self, factory: Callable[[], Iterator[bytes]]) -> None:
        self._factory = factory

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._factory():
            yield chunk


def client() -> RegistryClient:
    return RegistryClient(REG, username="push", password="secret")


def tar_bytes(name: str, body: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    return buf.getvalue()


@respx.mock
def test_list_repositories_parses_the_catalog() -> None:
    respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": ["a", "b"]})
    )
    assert asyncio.run(client().list_repositories()) == ["a", "b"]


@respx.mock
def test_list_tags_parses_and_tolerates_a_null_tag_list() -> None:
    respx.get(f"{REG}/v2/a/tags/list").mock(
        return_value=httpx.Response(200, json={"name": "a", "tags": None})
    )
    assert asyncio.run(client().list_tags("a")) == []


@respx.mock
def test_head_manifest_reads_the_digest_off_a_zero_byte_response() -> None:
    route = respx.head(f"{REG}/v2/a/manifests/latest").mock(
        return_value=httpx.Response(
            200, headers={"Docker-Content-Digest": "sha256:abc"}, content=b""
        )
    )
    digest, unchanged = asyncio.run(client().head_manifest("a", "latest"))
    assert digest == "sha256:abc"
    assert unchanged is False
    assert "application/vnd.oci.image.manifest.v1+json" in route.calls[0].request.headers["accept"]


@respx.mock
def test_a_conditional_head_sends_if_none_match_and_reports_304_as_unchanged() -> None:
    route = respx.head(f"{REG}/v2/a/manifests/latest").mock(
        return_value=httpx.Response(304, content=b"")
    )
    digest, unchanged = asyncio.run(
        client().head_manifest("a", "latest", known_digest="sha256:known")
    )
    assert unchanged is True
    assert digest == "sha256:known"
    assert route.calls[0].request.headers["if-none-match"] == '"sha256:known"'


@respx.mock
def test_basic_auth_rides_every_request() -> None:
    route = respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": []})
    )
    asyncio.run(client().list_repositories())
    assert route.calls[0].request.headers["authorization"].startswith("Basic ")


@respx.mock
def test_a_blob_follows_the_307_to_its_final_body() -> None:
    respx.get(f"{REG}/v2/a/blobs/sha256:cfg").mock(
        return_value=httpx.Response(307, headers={"Location": "https://minio.test/blob"})
    )
    respx.get("https://minio.test/blob").mock(
        return_value=httpx.Response(200, json={"package": {"name": "a"}})
    )
    assert asyncio.run(client().get_config_json("a", "sha256:cfg")) == {"package": {"name": "a"}}


@respx.mock
def test_a_layer_blob_is_untarred_to_one_member() -> None:
    respx.get(f"{REG}/v2/a/blobs/sha256:docs").mock(
        return_value=httpx.Response(200, content=tar_bytes("README.md", b"# hi\n"))
    )
    assert asyncio.run(client().get_layer_file("a", "sha256:docs")) == "# hi\n"


@respx.mock
def test_an_oversized_blob_raises_and_is_never_materialized() -> None:
    oversized = b"x" * (MAX_BLOB_BYTES + 65536)
    respx.get(f"{REG}/v2/a/blobs/sha256:big").mock(
        return_value=httpx.Response(200, content=oversized)
    )
    with pytest.raises(FetchError) as caught:
        asyncio.run(client().get_config_json("a", "sha256:big"))
    assert "exceeds" in str(caught.value)


@respx.mock
def test_the_oversized_blob_is_abandoned_mid_stream_not_read_whole() -> None:
    """The property a read-then-measure implementation fails.

    The shipped assertions above pass identically against an implementation
    that buffers the body and then measures it, so this counts how much of
    the stream was actually pulled.
    """
    chunk = b"z" * 65536
    total_chunks = (MAX_BLOB_BYTES // len(chunk)) * 3
    pulled = {"n": 0}

    def counting_stream() -> Iterator[bytes]:
        for _ in range(total_chunks):
            pulled["n"] += 1
            yield chunk

    respx.get(f"{REG}/v2/a/blobs/sha256:stream").mock(
        return_value=httpx.Response(200, stream=_Stream(counting_stream))
    )
    with pytest.raises(FetchError):
        asyncio.run(client().get_config_json("a", "sha256:stream"))

    assert pulled["n"] < total_chunks, "the whole body was consumed despite the cap"
    assert pulled["n"] <= (MAX_BLOB_BYTES // len(chunk)) + 1, "it stopped at the cap, not later"


@respx.mock
def test_a_blob_just_under_the_cap_reads_cleanly() -> None:
    """The positive control for the cap: the limit rejects only what is over it."""
    body = b'{"a":"' + b"y" * (MAX_BLOB_BYTES - 100) + b'"}'
    assert len(body) < MAX_BLOB_BYTES
    respx.get(f"{REG}/v2/a/blobs/sha256:ok").mock(return_value=httpx.Response(200, content=body))
    assert asyncio.run(client().get_config_json("a", "sha256:ok"))["a"].startswith("yyy")


def test_the_cap_constant_is_one_mebibyte() -> None:
    """A silent raise of this number fails here rather than in production."""
    assert MAX_BLOB_BYTES == 1_048_576


def test_the_client_is_built_async_and_bounded_at_eight_connections() -> None:
    built = client().build_client()
    try:
        assert isinstance(built, httpx.AsyncClient)
        pool = getattr(built._transport, "_pool", None)
        assert pool is not None, "the async transport exposes a connection pool"
        assert pool._max_connections == MAX_CONNECTIONS
        assert built.follow_redirects is True
    finally:
        asyncio.run(built.aclose())


@respx.mock
def test_a_non_2xx_becomes_a_fetch_error_naming_the_status() -> None:
    respx.get(f"{REG}/v2/_catalog").mock(return_value=httpx.Response(500))
    with pytest.raises(FetchError) as caught:
        asyncio.run(client().list_repositories())
    assert "500" in str(caught.value)


@respx.mock
def test_a_manifest_returns_its_body_and_digest() -> None:
    respx.get(f"{REG}/v2/a/manifests/latest").mock(
        return_value=httpx.Response(
            200,
            json={"artifactType": "x", "layers": []},
            headers={"Docker-Content-Digest": "sha256:m"},
        )
    )
    manifest, digest = asyncio.run(client().get_manifest("a", "latest"))
    assert digest == "sha256:m"
    assert manifest["artifactType"] == "x"
