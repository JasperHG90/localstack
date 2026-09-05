"""The walk itself: what it fetches, how often, and what it must never touch.

`RegistrySweep` carries this ticket's headline guardrails — never pull a
weights layer, draw each digest once, and cost nothing when nothing changed
— and none of them are observable from the unit tests of its parts. An
adversarial review mutated `_entry` to download every layer including
`model.v1.tar` and the suite still passed 71/71; these are the tests that
now fail on that mutation.
"""

from __future__ import annotations

import asyncio
import io
import tarfile
from pathlib import Path
from typing import Any

import httpx
import respx

from registry_ui.registry import KITOPS_ARTIFACT_TYPE
from registry_ui.registry_client import RegistryClient, RegistrySweep
from registry_ui.registry_store import RegistryStore

REG = "https://registry.example.test"

WEIGHTS_DIGEST = "sha256:weights"
TOKENIZER_DIGEST = "sha256:tokenizer"
EMBARK_DIGEST = "sha256:embark"
KITFILE_DIGEST = "sha256:kitfile"
DOCS_DIGEST = "sha256:docs"
KIT_DIGEST = "sha256:kit"

FORBIDDEN_BLOBS = (WEIGHTS_DIGEST, TOKENIZER_DIGEST, EMBARK_DIGEST)

MANIFEST: dict[str, Any] = {
    "artifactType": KITOPS_ARTIFACT_TYPE,
    "config": {"digest": KITFILE_DIGEST, "size": 2033},
    "layers": [
        {
            "mediaType": "application/vnd.kitops.modelkit.model.v1.tar",
            "digest": WEIGHTS_DIGEST,
            "size": 309664768,
            "annotations": {"org.cncf.model.filepath": "model.onnx"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.modelpart.v1.tar",
            "digest": TOKENIZER_DIGEST,
            "size": 33387008,
            "annotations": {"org.cncf.model.filepath": "tokenizer.json"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.modelpart.v1.tar",
            "digest": EMBARK_DIGEST,
            "size": 2048,
            "annotations": {"org.cncf.model.filepath": "embark.json"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.docs.v1.tar",
            "digest": DOCS_DIGEST,
            "size": 6656,
            "annotations": {"org.cncf.model.filepath": "README.md"},
        },
    ],
    "annotations": {"org.opencontainers.image.created": "2026-09-05T06:35:01Z"},
}

KITFILE: dict[str, Any] = {"package": {"description": "a kit", "authors": ["lab"]}}

IMAGE_MANIFEST: dict[str, Any] = {
    "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": "sha256:imgcfg"},
    "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "size": 5000}],
}
IMAGE_CONFIG: dict[str, Any] = {
    "architecture": "arm64",
    "os": "linux",
    "created": "2026-06-22T19:54:07Z",
}
INDEX_MANIFEST: dict[str, Any] = {
    "mediaType": "application/vnd.oci.image.index.v1+json",
    "manifests": [{"digest": "sha256:a"}, {"digest": "sha256:b"}],
}


def tar_bytes(name: str, body: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    return buf.getvalue()


def mount_modelkit(repo: str = "kit", tags: tuple[str, ...] = ("0.1.0", "latest")) -> None:
    """One repo, two tags, one digest — the live registry's actual shape."""
    respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": [repo]})
    )
    respx.get(f"{REG}/v2/{repo}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": list(tags)})
    )
    for tag in tags:
        respx.head(f"{REG}/v2/{repo}/manifests/{tag}").mock(
            return_value=httpx.Response(200, headers={"Docker-Content-Digest": KIT_DIGEST})
        )
    respx.get(f"{REG}/v2/{repo}/manifests/{KIT_DIGEST}").mock(
        return_value=httpx.Response(
            200, json=MANIFEST, headers={"Docker-Content-Digest": KIT_DIGEST}
        )
    )
    respx.get(f"{REG}/v2/{repo}/blobs/{KITFILE_DIGEST}").mock(
        return_value=httpx.Response(200, json=KITFILE)
    )
    respx.get(f"{REG}/v2/{repo}/blobs/{DOCS_DIGEST}").mock(
        return_value=httpx.Response(200, content=tar_bytes("README.md", b"# kit\n"))
    )
    # Deliberately reachable: if the walk asks for a weights layer it gets a
    # 200, so the guardrail below fails on a real fetch rather than on a 404.
    for digest in FORBIDDEN_BLOBS:
        respx.get(f"{REG}/v2/{repo}/blobs/{digest}").mock(
            return_value=httpx.Response(200, content=b"x" * 512)
        )


def sweep(tmp_path: Path) -> RegistrySweep:
    store = RegistryStore(tmp_path / "registry.db")
    store.create_schema()
    return RegistrySweep(RegistryClient(REG, "push", "secret"), store)


def blob_calls() -> list[str]:
    return [
        str(call.request.url).rsplit("/", 1)[-1]
        for call in respx.calls
        if "/blobs/" in str(call.request.url)
    ]


@respx.mock
def test_the_walk_never_fetches_a_weights_or_embark_layer(tmp_path: Path) -> None:
    """The guardrail. Its fixtures serve those blobs, so a fetch really happens."""
    mount_modelkit()
    asyncio.run(sweep(tmp_path).payload())

    fetched = blob_calls()
    assert KITFILE_DIGEST in fetched, "positive control: the Kitfile really is fetched"
    assert DOCS_DIGEST in fetched, "positive control: the README really is fetched"
    for forbidden in FORBIDDEN_BLOBS:
        assert forbidden not in fetched, f"the walk pulled {forbidden}"


@respx.mock
def test_two_tags_on_one_digest_draw_one_kit_and_fetch_two_blobs(tmp_path: Path) -> None:
    mount_modelkit()
    payload = asyncio.run(sweep(tmp_path).payload())

    assert len(payload["models"]) == 1
    assert payload["models"][0]["tags"] == ["0.1.0", "latest"]
    assert len(blob_calls()) == 2, "one Kitfile and one README, not one pair per tag"


@respx.mock
def test_a_cold_walk_costs_one_plus_repos_plus_tags_plus_two_per_digest(tmp_path: Path) -> None:
    mount_modelkit()
    asyncio.run(sweep(tmp_path).payload())

    urls = [str(call.request.url) for call in respx.calls]
    assert sum("_catalog" in u for u in urls) == 1
    assert sum("tags/list" in u for u in urls) == 1
    assert sum("/manifests/" in u for u in urls) == 3, "two tag HEADs plus one manifest GET"
    assert len(blob_calls()) == 2


@respx.mock
def test_a_warm_sweep_fetches_no_manifest_and_no_blob(tmp_path: Path) -> None:
    """A digest is content-addressed, so a stored entry needs nothing re-read."""
    mount_modelkit()
    warm = sweep(tmp_path)
    asyncio.run(warm.payload())

    respx.calls.clear()
    payload = asyncio.run(warm.payload(force=True))

    assert payload["models"][0]["repo"] == "kit"
    assert payload["models"][0]["tags"] == ["0.1.0", "latest"], (
        "tags come from this sweep's own reference, never from the stored entry"
    )
    assert payload["models"][0]["card_html"], "the card came back from the store"
    assert blob_calls() == []
    manifest_gets = [
        call
        for call in respx.calls
        if call.request.method == "GET" and "/manifests/" in str(call.request.url)
    ]
    assert manifest_gets == [], "a stored digest needs no manifest re-read"


@respx.mock
def test_a_restart_against_a_populated_store_fetches_no_blob(tmp_path: Path) -> None:
    mount_modelkit()
    asyncio.run(sweep(tmp_path).payload())

    respx.calls.clear()
    restarted = sweep(tmp_path)  # a fresh object over the same database file
    payload = asyncio.run(restarted.payload())

    assert payload["models"][0]["card_html"]
    assert blob_calls() == [], "the store survived the restart"


@respx.mock
def test_the_sweep_floor_serves_the_previous_payload(tmp_path: Path) -> None:
    mount_modelkit()
    held = sweep(tmp_path)
    asyncio.run(held.payload())

    respx.calls.clear()
    asyncio.run(held.payload())

    assert respx.calls.call_count == 0, "inside the floor, nothing is re-requested"


@respx.mock
def test_a_pushed_image_lands_in_images_and_never_in_models(tmp_path: Path) -> None:
    respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": ["img"]})
    )
    respx.get(f"{REG}/v2/img/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1"]})
    )
    respx.head(f"{REG}/v2/img/manifests/v1").mock(
        return_value=httpx.Response(200, headers={"Docker-Content-Digest": "sha256:img"})
    )
    respx.get(f"{REG}/v2/img/manifests/sha256:img").mock(
        return_value=httpx.Response(200, json=IMAGE_MANIFEST)
    )
    respx.get(f"{REG}/v2/img/blobs/sha256:imgcfg").mock(
        return_value=httpx.Response(200, json=IMAGE_CONFIG)
    )

    payload = asyncio.run(sweep(tmp_path).payload())

    assert payload["models"] == []
    assert len(payload["images"]) == 1
    assert payload["images"][0]["arch"] == "arm64"
    assert payload["images"][0]["size"] == 5000


@respx.mock
def test_a_multi_arch_index_renders_a_marker_and_fetches_no_config(tmp_path: Path) -> None:
    respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": ["multi"]})
    )
    respx.get(f"{REG}/v2/multi/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["latest"]})
    )
    respx.head(f"{REG}/v2/multi/manifests/latest").mock(
        return_value=httpx.Response(200, headers={"Docker-Content-Digest": "sha256:idx"})
    )
    respx.get(f"{REG}/v2/multi/manifests/sha256:idx").mock(
        return_value=httpx.Response(200, json=INDEX_MANIFEST)
    )

    payload = asyncio.run(sweep(tmp_path).payload())

    assert payload["images"][0]["multi_arch"] is True
    assert payload["images"][0]["size"] is None
    assert blob_calls() == []


@respx.mock
def test_a_vanished_digest_is_evicted_from_the_store(tmp_path: Path) -> None:
    mount_modelkit()
    live = sweep(tmp_path)
    asyncio.run(live.payload())
    assert live.store.get_card(KIT_DIGEST) is not None

    respx.get(f"{REG}/v2/_catalog").mock(
        return_value=httpx.Response(200, json={"repositories": []})
    )
    asyncio.run(live.payload(force=True))

    assert live.store.get_card(KIT_DIGEST) is None


@respx.mock
def test_a_failed_sweep_serves_the_last_good_payload_with_the_error(tmp_path: Path) -> None:
    """An unreachable registry must not empty a tab that was right a minute ago."""
    mount_modelkit()
    live = sweep(tmp_path)
    good = asyncio.run(live.payload())
    assert good["models"][0]["repo"] == "kit"

    respx.get(f"{REG}/v2/_catalog").mock(return_value=httpx.Response(503))
    degraded = asyncio.run(live.payload(force=True))

    assert degraded["models"][0]["repo"] == "kit", "the last good payload survived"
    assert degraded["error"], "and the failure is reported alongside it"


@respx.mock
def test_a_first_ever_sweep_that_fails_raises_rather_than_inventing_a_payload(
    tmp_path: Path,
) -> None:
    respx.get(f"{REG}/v2/_catalog").mock(return_value=httpx.Response(503))
    try:
        asyncio.run(sweep(tmp_path).payload())
    except Exception as err:
        assert "503" in str(err)
    else:
        raise AssertionError("a failure with no cached payload must raise")
