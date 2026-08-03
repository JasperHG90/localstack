"""A stand-in for `releases.hashicorp.com`, served over real HTTP.

Matching `tests/conftest.py`: a real server on localhost rather than a mocked
`urllib`. The layout copies what was measured against the real host on
2026-08-03: `/<tool>/<version>/<tool>_<version>_SHA256SUMS` with
`<sha256>  <filename>` lines, beside `/<tool>/<version>/<archive>.zip`.
"""

import hashlib
import io
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer


def build_archive(tool: str, body: str) -> bytes:
    """A zip holding one executable entry named after the tool."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(tool, body)
    return buffer.getvalue()


def fake_binary(tool: str, version: str) -> str:
    """A script that answers `version` the way the real CLI does."""
    return f'#!/bin/sh\nif [ "$1" = version ]; then echo "{tool.title()} v{version}"; fi\n'


class ReleaseServer(HTTPServer):
    """Serves a dict of path to bytes, and records what was asked for."""

    files: dict[str, bytes]
    requests: list[str]


class Handler(BaseHTTPRequestHandler):
    server: ReleaseServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        self.server.requests.append(self.path)
        body = self.server.files.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Silence. The suite's output is the test names, not an access log."""


def publish(
    files: dict[str, bytes],
    tool: str,
    version: str,
    target: str,
    archive_bytes: bytes,
    checksum: str | None = None,
) -> None:
    """Add one archive plus its SHA256SUMS line to the served layout.

    `checksum` overrides the real digest, which is how the mismatch row gets
    a release whose published checksum does not match its bytes.
    """
    archive = f"{tool}_{version}_{target}.zip"
    digest = checksum or hashlib.sha256(archive_bytes).hexdigest()
    sums_path = f"/{tool}/{version}/{tool}_{version}_SHA256SUMS"
    existing = files.get(sums_path, b"").decode()
    files[sums_path] = (existing + f"{digest}  {archive}\n").encode()
    files[f"/{tool}/{version}/{archive}"] = archive_bytes
