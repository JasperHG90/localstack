"""Turning registry manifests into the shapes the tab renders.

Pure: no HTTP, no database, no event loop, shaped like `status.py`.

Traps this file exists to absorb:

- A ModelKit is told apart from a container image by the manifest's
  `artifactType`, not by its layers or its repository name.
- A manifest index carries no `artifactType`, no `config` and no `layers`,
  so an image row built from one has no architecture and no size. It says
  `multi_arch` rather than inventing either.
- `embark.json` is embark's own serving config, not registry metadata. It
  is listed as a layer and never parsed.
"""

from __future__ import annotations

from typing import Any

from markdown_it import MarkdownIt

KITOPS_ARTIFACT_TYPE = "application/vnd.kitops.modelkit.manifest.v1+json"
FILEPATH_ANNOTATION = "org.cncf.model.filepath"

_LAYER_KINDS = ("model", "modelpart", "code", "docs")

# js-default enables GFM tables and fenced code, and leaves `html` off, so
# markup inside a card is escaped rather than served.
_MARKDOWN = MarkdownIt("js-default")


def render_card(markdown: str) -> str:
    """Render a model card's markdown to HTML."""
    return str(_MARKDOWN.render(markdown))


def layer_kind(media_type: str) -> str:
    """The Kitfile field a layer belongs to, or `other` for a non-ModelKit layer."""
    for kind in _LAYER_KINDS:
        if f"modelkit.{kind}.v1" in media_type:
            return kind
    return "other"


def is_modelkit(manifest: dict[str, Any]) -> bool:
    """Whether this manifest is a KitOps ModelKit rather than a container image."""
    return manifest.get("artifactType") == KITOPS_ARTIFACT_TYPE


def group_by_digest(
    triples: list[tuple[str, str, str]],
) -> dict[tuple[str, str], list[str]]:
    """Collapse (repo, tag, digest) triples onto one entry per (repo, digest).

    Both tags of every repo in this registry resolve to one digest, so a
    repo-tag walk would draw each kit twice and fetch its blobs twice.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    for repo, tag, digest in triples:
        grouped.setdefault((repo, digest), []).append(tag)
    return grouped


def _layers(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for layer in manifest.get("layers") or []:
        annotations = layer.get("annotations") or {}
        rows.append(
            {
                "path": annotations.get(FILEPATH_ANNOTATION),
                "kind": layer_kind(str(layer.get("mediaType", ""))),
                "size": layer.get("size"),
                "digest": layer.get("digest"),
            }
        )
    return rows


def kit_card(
    repo: str,
    tags: list[str],
    digest: str,
    manifest: dict[str, Any],
    kitfile: dict[str, Any],
    readme: str | None,
) -> dict[str, Any]:
    """One ModelKit as the tab renders it.

    `readme` is None for a kit carrying no docs layer; the card is built from
    the Kitfile alone and `card_html` is None.
    """
    package = kitfile.get("package") or {}
    annotations = manifest.get("annotations") or {}
    return {
        "repo": repo,
        "tags": tags,
        "digest": digest,
        "created": annotations.get("org.opencontainers.image.created"),
        "description": package.get("description", ""),
        "authors": package.get("authors") or [],
        "layers": _layers(manifest),
        "card_html": render_card(readme) if readme is not None else None,
    }


def image_row(
    repo: str,
    tags: list[str],
    digest: str,
    manifest: dict[str, Any],
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """One container image as the images tab renders it.

    `config` is the image's config blob, or None when the manifest is an
    index. An index names no single architecture and carries no layers, so
    those cells stay empty rather than being guessed at.
    """
    if config is None:
        return {
            "repo": repo,
            "tags": tags,
            "digest": digest,
            "arch": None,
            "size": None,
            "pushed": None,
            "multi_arch": True,
        }
    size = sum(int(layer.get("size") or 0) for layer in manifest.get("layers") or [])
    return {
        "repo": repo,
        "tags": tags,
        "digest": digest,
        "arch": config.get("architecture"),
        "size": size,
        "pushed": config.get("created"),
        "multi_arch": False,
    }
