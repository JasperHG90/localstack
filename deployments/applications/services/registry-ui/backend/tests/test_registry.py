"""The pure layer: no network, no event loop, no respx."""

from __future__ import annotations

from typing import Any

import pytest

from registry_ui.registry import (
    KITOPS_ARTIFACT_TYPE,
    group_by_digest,
    image_row,
    is_modelkit,
    kit_card,
    layer_kind,
    render_card,
)

MODELKIT_MANIFEST: dict[str, Any] = {
    "artifactType": KITOPS_ARTIFACT_TYPE,
    "config": {
        "mediaType": "application/vnd.kitops.modelkit.config.v1+json",
        "digest": "sha256:cfg",
        "size": 2033,
    },
    "layers": [
        {
            "mediaType": "application/vnd.kitops.modelkit.model.v1.tar",
            "digest": "sha256:weights",
            "size": 309664768,
            "annotations": {"org.cncf.model.filepath": "model.onnx"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.modelpart.v1.tar",
            "digest": "sha256:tok",
            "size": 33387008,
            "annotations": {"org.cncf.model.filepath": "tokenizer.json"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.docs.v1.tar",
            "digest": "sha256:docs",
            "size": 6656,
            "annotations": {"org.cncf.model.filepath": "README.md"},
        },
        {
            "mediaType": "application/vnd.kitops.modelkit.code.v1.tar",
            "digest": "sha256:code",
            "size": 2048,
            "annotations": {"org.cncf.model.filepath": "justfile"},
        },
    ],
    "annotations": {"org.opencontainers.image.created": "2026-09-05T06:35:01Z"},
}

KITFILE: dict[str, Any] = {
    "manifestVersion": "1.0.0",
    "package": {
        "name": "embeddinggemma-q8",
        "description": "Embeddinggemma, ONNX, Q8",
        "authors": ["Google"],
    },
}

IMAGE_MANIFEST: dict[str, Any] = {
    "config": {
        "mediaType": "application/vnd.oci.image.config.v1+json",
        "digest": "sha256:imgcfg",
        "size": 3611,
    },
    "layers": [
        {
            "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
            "digest": "sha256:l1",
            "size": 1000,
        },
        {
            "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
            "digest": "sha256:l2",
            "size": 2000,
        },
    ],
}

IMAGE_CONFIG: dict[str, Any] = {
    "architecture": "arm64",
    "os": "linux",
    "created": "2026-06-22T19:54:07.889802725Z",
}

INDEX_MANIFEST: dict[str, Any] = {
    "mediaType": "application/vnd.oci.image.index.v1+json",
    "manifests": [
        {"digest": "sha256:a", "platform": {"architecture": "arm64", "os": "linux"}},
        {"digest": "sha256:b", "platform": {"architecture": "amd64", "os": "linux"}},
    ],
}


@pytest.mark.parametrize(
    ("media_type", "expected"),
    [
        ("application/vnd.kitops.modelkit.model.v1.tar", "model"),
        ("application/vnd.kitops.modelkit.modelpart.v1.tar", "modelpart"),
        ("application/vnd.kitops.modelkit.code.v1.tar", "code"),
        ("application/vnd.kitops.modelkit.docs.v1.tar", "docs"),
        ("application/vnd.oci.image.layer.v1.tar+gzip", "other"),
    ],
)
def test_layer_kind_maps_each_media_type(media_type: str, expected: str) -> None:
    assert layer_kind(media_type) == expected


def test_a_modelkit_manifest_is_recognised_by_its_artifact_type() -> None:
    assert is_modelkit(MODELKIT_MANIFEST) is True


def test_an_image_manifest_is_not_a_modelkit() -> None:
    assert is_modelkit(IMAGE_MANIFEST) is False
    assert is_modelkit(INDEX_MANIFEST) is False


def test_kit_card_carries_package_metadata_layers_and_the_rendered_readme() -> None:
    card = kit_card(
        repo="embeddinggemma-q8",
        tags=["0.1.0", "latest"],
        digest="sha256:kit",
        manifest=MODELKIT_MANIFEST,
        kitfile=KITFILE,
        readme="# embeddinggemma-q8\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
    )
    assert card["repo"] == "embeddinggemma-q8"
    assert card["tags"] == ["0.1.0", "latest"]
    assert card["digest"] == "sha256:kit"
    assert card["description"] == "Embeddinggemma, ONNX, Q8"
    assert card["authors"] == ["Google"]
    assert card["created"] == "2026-09-05T06:35:01Z"
    assert [layer["path"] for layer in card["layers"]] == [
        "model.onnx",
        "tokenizer.json",
        "README.md",
        "justfile",
    ]
    assert [layer["kind"] for layer in card["layers"]] == ["model", "modelpart", "docs", "code"]
    assert "<table>" in card["card_html"]


def test_a_kit_with_no_docs_layer_still_builds_a_card_and_says_so() -> None:
    manifest = dict(MODELKIT_MANIFEST)
    manifest["layers"] = [
        layer for layer in MODELKIT_MANIFEST["layers"] if "docs" not in layer["mediaType"]
    ]
    card = kit_card(
        repo="k",
        tags=["latest"],
        digest="sha256:k",
        manifest=manifest,
        kitfile=KITFILE,
        readme=None,
    )
    assert card["card_html"] is None
    assert card["description"] == "Embeddinggemma, ONNX, Q8"
    assert card["layers"], "layers survive even with no docs layer"


def test_render_card_produces_tables_and_escapes_raw_html() -> None:
    html = render_card("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in html
    # positive control: the renderer emits real markup for markdown it accepts,
    # so the escaping assertion below is not vacuous.
    assert "<td>1</td>" in html
    escaped = render_card("<script>alert(1)</script>")
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


def test_image_row_reads_arch_and_pushed_from_the_config_blob() -> None:
    row = image_row(
        repo="dash-backend",
        tags=["v0.4.1"],
        digest="sha256:img",
        manifest=IMAGE_MANIFEST,
        config=IMAGE_CONFIG,
    )
    assert row["repo"] == "dash-backend"
    assert row["arch"] == "arm64"
    assert row["pushed"] == "2026-06-22T19:54:07.889802725Z"
    assert row["size"] == 3000
    assert row["multi_arch"] is False


def test_an_index_renders_a_multi_arch_row_with_no_invented_arch_or_size() -> None:
    row = image_row(
        repo="multi",
        tags=["latest"],
        digest="sha256:idx",
        manifest=INDEX_MANIFEST,
        config=None,
    )
    assert row["multi_arch"] is True
    assert row["arch"] is None
    assert row["size"] is None
    assert row["pushed"] is None


def test_group_by_digest_collapses_two_tags_onto_one_entry() -> None:
    grouped = group_by_digest([("repo", "0.1.0", "sha256:one"), ("repo", "latest", "sha256:one")])
    assert list(grouped) == [("repo", "sha256:one")]
    assert grouped[("repo", "sha256:one")] == ["0.1.0", "latest"]


def test_group_by_digest_keeps_distinct_digests_apart() -> None:
    grouped = group_by_digest([("repo", "0.1.0", "sha256:one"), ("repo", "latest", "sha256:two")])
    assert len(grouped) == 2
