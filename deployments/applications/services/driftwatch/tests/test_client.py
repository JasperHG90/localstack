from __future__ import annotations

import json

import httpx
import pytest
import respx

from driftwatch.client import EmbarkClient, EmbarkError
from tests import fixtures

BASE = "http://embark.test:8000"


def client() -> EmbarkClient:
    return EmbarkClient(base_url=BASE, api_key="secret", timeout=5.0)


@respx.mock
def test_embed_sends_the_input_type_and_the_bearer_token() -> None:
    route = respx.post(f"{BASE}/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [1.0, 0.0]}],
                "model": "m",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )
    )

    with client() as embark:
        embark.embed(["hello"], model="m", input_type="query")

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret"
    assert json.loads(request.content) == {
        "model": "m",
        "input": ["hello"],
        "input_type": "query",
    }


@respx.mock
def test_embed_orders_vectors_by_the_index_the_response_carries() -> None:
    respx.post(f"{BASE}/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
                ],
                "model": "m",
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )
    )

    with client() as embark:
        vectors = embark.embed(["a", "b"], model="m", input_type="document")

    assert vectors[0].tolist() == [1.0, 0.0]
    assert vectors[1].tolist() == [0.0, 1.0]


@respx.mock
def test_a_short_response_is_an_error_not_a_silent_truncation() -> None:
    respx.post(f"{BASE}/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [1.0]}],
                "model": "m",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )
    )

    with client() as embark, pytest.raises(EmbarkError, match="asked for 2 vectors"):
        embark.embed(["a", "b"], model="m", input_type="document")


@respx.mock
def test_a_refusal_carries_the_status_and_the_body() -> None:
    respx.post(f"{BASE}/v1/embeddings").mock(
        return_value=httpx.Response(401, text="invalid api key")
    )

    with client() as embark, pytest.raises(EmbarkError, match="answered 401"):
        embark.embed(["a"], model="m", input_type="document")


@respx.mock
def test_a_transport_failure_is_an_embark_error() -> None:
    respx.post(f"{BASE}/v1/embeddings").mock(side_effect=httpx.ConnectError("refused"))

    with client() as embark, pytest.raises(EmbarkError, match="failed"):
        embark.embed(["a"], model="m", input_type="document")


@respx.mock
def test_rerank_asks_for_every_candidate_and_reads_the_scores() -> None:
    fixtures.install(respx, base_url=BASE, vectors=fixtures.one_hot(["a", "b", "c"]))

    with client() as embark:
        hits = embark.rerank("q", ["a", "b", "c"], model="r")

    request = respx.calls.last.request
    assert "top_n" not in json.loads(request.content)
    assert [hit.index for hit in hits] == [0, 1, 2]
    assert hits[0].score > hits[1].score
