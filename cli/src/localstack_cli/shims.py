"""The PATH shims that let a bare `nomad`, `consul` or `vault` see a session.

All three need one. Measured on 2026-07-31, and re-measured on 2026-08-03
against the exact pinned Nomad archive this command installs:

- `nomad` has no credential file at all. `NOMAD_TOKEN_FILE` appears zero
  times in the pinned binary, and with it set and the file present, `nomad`
  sent no `X-Nomad-Token` header. It reads `NOMAD_TOKEN` or `-token`.
- `consul` reads a token file, and that is the problem: the `_FILE` form of
  `CONSUL_HTTP_TOKEN` outranks the variable itself, so a stale file silently
  beats every fresh token, and a missing one makes `consul` fail outright
  rather than fall back. D6 writes no tokens, so it exports
  `CONSUL_HTTP_TOKEN` instead and never sets or names the file variable.
- `vault` reads `~/.vault-token`, but that file is inert while `VAULT_TOKEN`
  is set, and this devcontainer sets it for everyone. So a bare `vault` runs
  as the injected root token until the shim overrides it for one call.

One template renders all three, parameterised by tool name and token
variable, so they cannot drift apart.

Two things the template must never do. It must not resolve the tool through
`PATH`, because `PATH` starts at the shims directory: at install time that
would record the shim's own future path, and at run time it would recurse
until the process dies. And it must not fail hard, because a shim that dies
when the CLI has a bug turns any bug into a dead `nomad`, which is a worse
machine than the developer started with.
"""

from pathlib import Path

# The variable each CLI actually reads. `consul` gets `CONSUL_HTTP_TOKEN`,
# never its `_FILE` form: see the module docstring and D2 R12.
TOKEN_VARS = {
    "nomad": "NOMAD_TOKEN",
    "consul": "CONSUL_HTTP_TOKEN",
    "vault": "VAULT_TOKEN",
}

SHIM_MODE = 0o755

TEMPLATE = """#!/usr/bin/env bash
# Written by `localstack deps --with-shims`. Remove with
# `localstack deps --remove-shims`.
#
# REAL is an absolute literal, fixed at install time. Never resolve {tool}
# through PATH here: PATH starts at this file, so that recurses.
REAL="{real}"
T="$(localstack token {tool} 2>/dev/null)" || exec "$REAL" "$@"
# An empty token is not a token. Exporting it would clear one the developer
# already had, which looks like success and is worse than falling through.
[ -n "$T" ] || exec "$REAL" "$@"
exec env {variable}="$T" "$REAL" "$@"
"""


class ShimError(RuntimeError):
    """A shim could not be written."""


def render(tool: str, real: Path) -> str:
    """The shim body for one tool, naming its binary by absolute path."""
    if tool not in TOKEN_VARS:
        raise ShimError(f"no shim template for {tool!r}")
    return TEMPLATE.format(
        tool=tool, real=str(real.expanduser().resolve()), variable=TOKEN_VARS[tool]
    )


def write_shims(tools: list[str], binaries: Path, shims: Path) -> list[Path]:
    """Write one shim per tool. Refuses when the pinned binary is absent.

    A shim pointing at a path that does not exist is a dead command, which is
    the one outcome the fall-through rules exist to prevent.
    """
    missing = [tool for tool in tools if not (binaries / tool).is_file()]
    if missing:
        raise ShimError(
            f"not installed under {binaries}: {', '.join(sorted(missing))}. "
            "Run `localstack deps --install` first. A shim over a missing "
            "binary is a dead command."
        )

    shims.mkdir(parents=True, exist_ok=True)
    written = []
    for tool in tools:
        path = shims / tool
        path.write_text(render(tool, binaries / tool))
        path.chmod(SHIM_MODE)
        written.append(path)
    return written


def remove_shims(shims: Path) -> list[Path]:
    """Delete every shim and return what was removed, so it can be named.

    Only ever touches the shims directory. The binaries live elsewhere, which
    is what makes removal safe: share one directory and the `nomad` shim and
    the `nomad` binary are the same file.
    """
    if not shims.is_dir():
        return []
    removed = []
    for path in sorted(shims.iterdir()):
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed
