"""Render a Vault-templated policy for one job, without pretending to be Vault.

`nomad-workloads` grants each workload access to its own secrets by
templating the path on the calling entity's alias metadata. Reading it raw
tells a developer nothing about which paths THEIR job can reach, so this
substitutes the job id and namespace and shows both the raw line and the
resolved one.

Three things this module refuses to hardcode, each of which has already
changed or will:

- The mount accessor. It is derived at bootstrap from `vault auth list` and
  differs per rebuild, so it is discovered by regex over the fetched text
  rather than written down here.
- The path count. F9 took this policy from six blocks to three. Code that
  counts blocks breaks the next time it is narrowed or widened.
- The variable set. A variable this module cannot fill stays visible as
  `{{...}}` and its row is marked unresolved. Blanking it would produce a
  resolved-looking path that is wrong, which is worse than an obviously
  incomplete one.

The result is a rendering of policy text, not an authorization decision.
Vault resolves these templates per request against the calling entity; this
resolves them from arguments.
"""

import re
from dataclasses import dataclass

# `path "..." {` opening a block, then `capabilities = [...]` inside it.
PATH_BLOCK = re.compile(r'path\s+"(?P<path>[^"]+)"\s*\{(?P<body>[^}]*)\}', re.S)
CAPABILITIES = re.compile(r"capabilities\s*=\s*\[(?P<list>[^\]]*)\]")
CAPABILITY = re.compile(r'"([^"]+)"')
# `{{identity.entity.aliases.<accessor>.metadata.<key>}}`, the only template
# shape this policy uses. The accessor is captured, never assumed.
TEMPLATE_VAR = re.compile(
    r"\{\{\s*identity\.entity\.aliases\.(?P<accessor>[^.]+)\.metadata\.(?P<key>\w+)\s*\}\}"
)
# Anything else still in braces after substitution.
UNRESOLVED = re.compile(r"\{\{[^}]*\}\}")


@dataclass(frozen=True)
class Grant:
    """One path block, raw and resolved.

    `unresolved` is a field rather than a property so it survives
    `dataclasses.asdict`, and therefore appears in `--json`. As a property it
    was invisible to every machine reader, which left the mark the
    requirement asks for existing only in the table.
    """

    raw_path: str
    resolved_path: str
    capabilities: list[str]
    unresolved: bool = False


def accessor(policy: str) -> str | None:
    """The auth mount accessor this policy templates on, from the text itself."""
    match = TEMPLATE_VAR.search(policy)
    return match.group("accessor") if match else None


def variables(policy: str) -> set[str]:
    """Every metadata key the policy substitutes."""
    return {match.group("key") for match in TEMPLATE_VAR.finditer(policy)}


def render(policy: str, values: dict[str, str]) -> list[Grant]:
    """Resolve every path block against `values`, keyed by metadata key.

    Blocks are returned in the order the policy states them, with no count
    assumed anywhere.
    """
    grants = []
    for block in PATH_BLOCK.finditer(policy):
        raw = block.group("path")

        def fill(match: re.Match[str]) -> str:
            return values.get(match.group("key"), match.group(0))

        resolved = TEMPLATE_VAR.sub(fill, raw)

        found = CAPABILITIES.search(block.group("body"))
        caps = CAPABILITY.findall(found.group("list")) if found else []
        grants.append(
            Grant(
                raw_path=raw,
                resolved_path=resolved,
                capabilities=caps,
                unresolved=bool(UNRESOLVED.search(resolved)),
            )
        )
    return grants
