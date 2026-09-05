"""Reads the cluster registry over the plain OCI distribution API.

Shaped like `consul_client.py`, but async and owning its own client:
`_http.py` stays the sync, JSON-only helper `/api/status` depends on.

Traps this file exists to absorb:

- A blob GET answers `307` to MinIO, so redirects must be followed. `307`
  is below 400, so a status check alone would miss it and the failure
  would surface as a JSON parse error rather than a status code.
- A layer blob is a plain tar, not JSON and not gzip. Only the OCI config
  blob is raw JSON.
- Every blob read is capped and counted as it streams. The cap reaches the
  final post-`307` body and no further: httpx reads a 3xx response's own
  body inside `_send_handling_redirects`, before any counter here sees it.
- The concurrency ceiling is eight because the latency curve plateaus
  there and the registry is a shared job with a small reservation.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import tarfile
import time
from typing import Any

import httpx

from registry_ui._http import FetchError
from registry_ui.registry import (
    group_by_digest,
    image_row,
    is_modelkit,
    kit_card,
    layer_kind,
)

MAX_BLOB_BYTES = 1_048_576
MAX_CONNECTIONS = 8
TIMEOUT_SECONDS = 20.0

MANIFEST_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    )
)


class RegistryClient:
    """One registry, one credential, one bounded connection pool."""

    def __init__(self, address: str, username: str, password: str) -> None:
        self.address = address.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._auth_header = f"Basic {token}"

    def build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            limits=httpx.Limits(max_connections=MAX_CONNECTIONS),
            headers={"Authorization": self._auth_header},
        )

    async def _get(
        self, path: str, client: httpx.AsyncClient | None = None, accept: str | None = None
    ) -> httpx.Response:
        own = client is None
        active = client or self.build_client()
        url = f"{self.address}{path}"
        try:
            response = await active.get(url, headers={"Accept": accept} if accept else None)
        except httpx.HTTPError as error:
            raise FetchError(f"{url}: {error}") from error
        finally:
            if own:
                await active.aclose()
        if response.status_code >= 400:
            raise FetchError(f"{url} returned {response.status_code}")
        return response

    async def _read_capped(self, path: str, client: httpx.AsyncClient | None = None) -> bytes:
        """Stream one blob, counting bytes, refusing past the cap.

        Counts as it goes rather than reading the body and measuring it, so
        an oversized body is never materialized.
        """
        own = client is None
        active = client or self.build_client()
        url = f"{self.address}{path}"
        chunks: list[bytes] = []
        total = 0
        try:
            async with active.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise FetchError(f"{url} returned {response.status_code}")
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_BLOB_BYTES:
                        raise FetchError(
                            f"{url}: blob exceeds cap: read {total} > {MAX_BLOB_BYTES}"
                        )
                    chunks.append(chunk)
        except httpx.HTTPError as error:
            raise FetchError(f"{url}: {error}") from error
        finally:
            if own:
                await active.aclose()
        return b"".join(chunks)

    async def list_repositories(self, client: httpx.AsyncClient | None = None) -> list[str]:
        response = await self._get("/v2/_catalog?n=1000", client)
        return list(response.json().get("repositories") or [])

    async def list_tags(self, repo: str, client: httpx.AsyncClient | None = None) -> list[str]:
        response = await self._get(f"/v2/{repo}/tags/list", client)
        return list(response.json().get("tags") or [])

    async def head_manifest(
        self,
        repo: str,
        tag: str,
        known_digest: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[str | None, bool]:
        """The sweep primitive: this tag's digest, and whether it is unchanged.

        `known_digest` sends `If-None-Match`; a `304` means the tag still
        points where the store thinks and no body is transferred.
        """
        own = client is None
        active = client or self.build_client()
        url = f"{self.address}/v2/{repo}/manifests/{tag}"
        headers = {"Accept": MANIFEST_ACCEPT}
        if known_digest:
            headers["If-None-Match"] = f'"{known_digest}"'
        try:
            response = await active.head(url, headers=headers)
        except httpx.HTTPError as error:
            raise FetchError(f"{url}: {error}") from error
        finally:
            if own:
                await active.aclose()
        if response.status_code == 304:
            return known_digest, True
        if response.status_code >= 400:
            raise FetchError(f"{url} returned {response.status_code}")
        return response.headers.get("Docker-Content-Digest"), False

    async def get_manifest(
        self, repo: str, reference: str, client: httpx.AsyncClient | None = None
    ) -> tuple[dict[str, Any], str | None]:
        response = await self._get(
            f"/v2/{repo}/manifests/{reference}", client, accept=MANIFEST_ACCEPT
        )
        return response.json(), response.headers.get("Docker-Content-Digest")

    async def get_config_json(
        self, repo: str, digest: str, client: httpx.AsyncClient | None = None
    ) -> dict[str, Any]:
        """The one blob that is raw JSON: the Kitfile, or an image's config."""
        raw = await self._read_capped(f"/v2/{repo}/blobs/{digest}", client)
        try:
            return dict(json.loads(raw))
        except ValueError as error:
            raise FetchError(f"{repo}@{digest} did not return JSON") from error

    async def get_layer_file(
        self, repo: str, digest: str, client: httpx.AsyncClient | None = None
    ) -> str:
        """One member out of a layer blob, which is a plain tar."""
        raw = await self._read_capped(f"/v2/{repo}/blobs/{digest}", client)
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r") as archive:
                names = archive.getnames()
                if not names:
                    raise FetchError(f"{repo}@{digest}: empty tar")
                handle = archive.extractfile(names[0])
                if handle is None:
                    raise FetchError(f"{repo}@{digest}: no readable member")
                return handle.read().decode()
        except tarfile.TarError as error:
            raise FetchError(f"{repo}@{digest} is not a tar") from error


class RegistrySweep:
    """The digest-keyed walk: what is in the registry, fetched once per digest.

    Freshness comes from the sweep (catalog, tags, one conditional manifest
    HEAD per tag). Content comes from the store, whose card rows are keyed
    by digest and therefore never go stale. A sweep floor keeps several open
    tabs from each triggering their own walk.
    """

    def __init__(
        self,
        client: RegistryClient,
        store: Any,
        floor_seconds: float = 30.0,
        clock: Any = None,
    ) -> None:
        self.client = client
        self.store = store
        self.floor_seconds = floor_seconds
        self._clock = clock or time.monotonic
        self._last_sweep: float | None = None
        self._payload: dict[str, Any] | None = None
        self._error: str | None = None

    def _due(self, force: bool) -> bool:
        if force or self._last_sweep is None or self._payload is None:
            return True
        return (self._clock() - self._last_sweep) >= self.floor_seconds

    async def payload(self, force: bool = False) -> dict[str, Any]:
        """The models/images payload, sweeping only when the floor allows.

        Raises only when there is nothing to fall back on. A sweep that
        fails with a previous payload in hand returns that payload and
        reports the failure alongside it: an unreachable registry should
        not empty a tab that was correct a minute ago.
        """
        if not self._due(force):
            assert self._payload is not None
            return self._payload
        try:
            self._payload = await self._walk()
            self._last_sweep = self._clock()
            self._error = None
        except Exception as err:
            self._error = str(err)
            if self._payload is None:
                raise
            return {**self._payload, "error": self._error}
        return self._payload

    async def _walk(self) -> dict[str, Any]:
        semaphore = asyncio.Semaphore(MAX_CONNECTIONS)

        async def bounded(coro: Any) -> Any:
            async with semaphore:
                return await coro

        async with self.client.build_client() as http:
            repos = await self.client.list_repositories(http)
            tag_lists = await asyncio.gather(
                *[bounded(self.client.list_tags(repo, http)) for repo in repos]
            )
            pairs = [(repo, tag) for repo, tags in zip(repos, tag_lists) for tag in tags]

            async def resolve(repo: str, tag: str) -> tuple[str, str, str | None]:
                known = await self.store.aknown_digest(repo, tag)
                digest, _unchanged = await self.client.head_manifest(repo, tag, known, http)
                return repo, tag, digest

            resolved = await asyncio.gather(*[bounded(resolve(r, t)) for r, t in pairs])

            seen = [(r, t, d) for r, t, d in resolved if d]
            await self.store.areplace_tags(seen)

            grouped = group_by_digest(seen)
            entries = await asyncio.gather(
                *[
                    bounded(self._entry(http, repo, digest, tags))
                    for (repo, digest), tags in grouped.items()
                ]
            )

        await self.store.aevict_unreferenced_cards()

        models = [entry for kind, entry in entries if kind == "model"]
        images = [entry for kind, entry in entries if kind == "image"]
        models.sort(key=lambda row: row["repo"])
        images.sort(key=lambda row: row["repo"])
        return {"models": models, "images": images}

    async def _entry(
        self, http: httpx.AsyncClient, repo: str, digest: str, tags: list[str]
    ) -> tuple[str, dict[str, Any]]:
        """One repo@digest as a row, fetching only what the store lacks.

        The cache is consulted BEFORE the manifest: a digest is
        content-addressed, so a stored entry is complete and a warm sweep
        touches no manifest and no blob.
        """
        cached = await self.store.aget_card(digest)
        if cached is not None:
            row = dict(cached)
            kind = str(row.pop("kind"))
            row["repo"] = repo
            row["tags"] = tags
            row["digest"] = digest
            return kind, row

        manifest, _ = await self.client.get_manifest(repo, digest, http)

        if not is_modelkit(manifest):
            config = None
            config_ref = (manifest.get("config") or {}).get("digest")
            if config_ref:
                config = await self.client.get_config_json(repo, config_ref, http)
            row = image_row(repo, tags, digest, manifest, config)
            await self._remember("image", digest, row)
            return "image", row

        kitfile = await self.client.get_config_json(
            repo, (manifest.get("config") or {})["digest"], http
        )
        readme = None
        for layer in manifest.get("layers") or []:
            if layer_kind(str(layer.get("mediaType", ""))) == "docs":
                readme = await self.client.get_layer_file(repo, layer["digest"], http)
                break

        card = kit_card(repo, tags, digest, manifest, kitfile, readme)
        await self._remember("model", digest, card)
        return "model", card

    async def _remember(self, kind: str, digest: str, row: dict[str, Any]) -> None:
        """Persist only what a digest fixes; repo and tags vary by reference."""
        entry = {k: v for k, v in row.items() if k not in ("repo", "tags", "digest")}
        entry["kind"] = kind
        await self.store.aput_card(digest, entry)
