#!/usr/bin/env python3
"""Refuse any oauth2-proxy auth exemption.

dash and registry-ui each sit entirely behind their own oauth2-proxy, and
they do so because neither jobspec sets a skip-auth key rather than because
anything asserts it. This check turns that absence into a gate, over every
oauth2-proxy jobspec in the repo.

It lives in `scripts/` with its own pre-commit hook rather than in the dash
backend suite, because `dash-backend-pytest` is scoped to the backend
directory: a commit touching only `oauth2-proxy.hcl` would run none of it,
and that is exactly the commit that would add an exemption.

Run with `--self-test` to check the checker.
"""

from __future__ import annotations

import sys
from pathlib import Path

JOBSPECS = (
    Path("deployments/infrastructure/services/oauth2-proxy.hcl"),
    Path("deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl"),
)

# Named in full, never matched as a `SKIP` substring:
# OAUTH2_PROXY_SKIP_PROVIDER_BUTTON is a legitimate setting already in this
# file, and a substring match would fail on it forever.
FORBIDDEN = (
    "OAUTH2_PROXY_SKIP_AUTH_ROUTES",
    "OAUTH2_PROXY_SKIP_AUTH_REGEX",
    "OAUTH2_PROXY_SKIP_AUTH_PREFLIGHT",
)


def offending_keys(text: str) -> list[str]:
    return [key for key in FORBIDDEN if key in text]


def _self_test() -> int:
    clean = (
        'OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="false"\nOAUTH2_PROXY_UPSTREAMS="a,b,c"\n'
    )
    if offending_keys(clean):
        print(
            "self-test: the legitimate SKIP_PROVIDER_BUTTON setting was flagged",
            file=sys.stderr,
        )
        return 1
    for key in FORBIDDEN:
        if offending_keys(f'{key}="/api/registry"\n') != [key]:
            print(f"self-test: {key} was not detected", file=sys.stderr)
            return 1
    print("self-test: ok")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()

    failed = 0
    for jobspec in JOBSPECS:
        if not jobspec.exists():
            print(f"{jobspec}: not found", file=sys.stderr)
            failed = 1
            continue
        found = offending_keys(jobspec.read_text())
        if not found:
            continue
        failed = 1
        print(
            f"{jobspec}: auth exemption present: {', '.join(found)}\n"
            "Every view this proxy fronts must stay behind its session gate. "
            "If a registry webhook ever needs an unauthenticated path, scope "
            "the exemption to that one path with its own shared secret; never "
            "widen it to /api/* or to a view.",
            file=sys.stderr,
        )
    return failed


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
