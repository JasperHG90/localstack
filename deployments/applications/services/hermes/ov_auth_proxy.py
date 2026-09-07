#!/usr/bin/env python3
"""Put a freshly minted Vault identity token on every OpenViking call.

Hermes reads its credential from the environment, and a running process cannot
have its environment changed. Vault identity tokens carry NO lease, so
consul-template falls back to its five-minute default and re-reads one that
often, and every read mints a different JWT. A template that restarts on change
therefore restarts Hermes every five minutes. Measured, not predicted.

So Hermes talks to this instead. Its endpoint is a constant it can hold for the
life of the process; the token is not, and this reads it from disk on EVERY
request. Nomad rewrites that file with `change_mode = "noop"`, so a rotation
reaches the next call and nothing restarts.

Deliberately stdlib only, so it runs on a stock python image with no build.

It listens on loopback and is not a general proxy: it forwards one upstream,
adds one header, and drops any credential the caller sent, so a compromised
Hermes cannot present someone else's token through it.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.request
from pathlib import Path

UPSTREAM = os.environ["OV_UPSTREAM"].rstrip("/")
TOKEN_FILE = Path(os.environ["OV_TOKEN_FILE"])
LISTEN_HOST = os.environ.get("OV_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("OV_LISTEN_PORT", "1934"))

# Never copied in either direction. Content-Length and Transfer-Encoding are
# recomputed by the library from the body actually sent; forwarding the
# original values desynchronises the framing.
DROP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
}

# Whatever Hermes sends as a credential is discarded. The token this adds is
# the only one that reaches OpenViking.
DROP_FROM_REQUEST = DROP | {"authorization", "x-api-key"}


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ov-auth-proxy"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _forward(self) -> None:
        try:
            token = TOKEN_FILE.read_text().strip()
        except OSError as error:
            # 503, not 500: the token file is written by Nomad and its absence
            # is a deployment state, not a bug in this process.
            self.send_error(503, f"token unreadable: {error}")
            return
        if not token:
            self.send_error(503, "token file is empty")
            return

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in DROP_FROM_REQUEST
        }
        headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            UPSTREAM + self.path,
            data=body,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                self._relay(response.status, response.headers.items(), response.read())
        except urllib.error.HTTPError as error:
            # An upstream 4xx/5xx is a real answer and belongs to the caller.
            self._relay(error.code, error.headers.items(), error.read())
        except OSError as error:
            self.send_error(502, f"upstream unreachable: {error}")

    def _relay(self, status: int, headers: object, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers:  # type: ignore[attr-defined]
            if key.lower() not in DROP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_PATCH = _forward
    do_DELETE = _forward
    do_HEAD = _forward
    do_OPTIONS = _forward


class Threaded(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    with Threaded((LISTEN_HOST, LISTEN_PORT), Proxy) as httpd:
        sys.stderr.write(
            f"ov-auth-proxy: {LISTEN_HOST}:{LISTEN_PORT} -> {UPSTREAM}, "
            f"token from {TOKEN_FILE}\n"
        )
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
