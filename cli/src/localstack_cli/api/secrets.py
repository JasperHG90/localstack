"""Which Vault paths a job asks for, and whether they are there.

The question this answers is "why will this job not render its template",
and the only useful answer names the path that is missing. So a path that
does not resolve is reported, not omitted: a table of the paths that DO
exist turns a broken job into an empty, healthy-looking view.

Three states, and the third one matters. 200 is present, 404 is missing, and
403 is DENIED, which is never folded into missing. Telling a developer their
secret does not exist when they simply cannot see it is the worse error: it
sends them to write a secret that is already there.

Existence comes from the KV2 metadata prefix, never the read prefix. The
metadata endpoint returns versions and timestamps and no `data` field at all,
so the value cannot be read even by accident.
"""

import re
from dataclasses import dataclass
from enum import Enum

# A literal reference, as every job on this cluster writes one today:
#     {{ with secret "<mount>/<namespace>/<job>/<name>" }}
# A computed call is matched by COMPUTED below rather than ignored.
LITERAL = re.compile(r'secret\s+"(?P<path>[^"]+)"')
# `{{ with secret (printf ...) }}` and anything else where the path is built
# at render time rather than written down.
COMPUTED = re.compile(r"secret\s+\(")


class State(Enum):
    """What Vault said about one path."""

    PRESENT = "present"
    MISSING = "missing"
    DENIED = "denied"
    # The reference is computed at render time, so there is no literal path
    # to check. Distinct from UNCHECKED: this one can never be resolved.
    UNKNOWN = "unknown"
    # Extracted but not looked up yet. Never rendered.
    UNCHECKED = "unchecked"


@dataclass(frozen=True)
class SecretRef:
    """One Vault path a job's template asks for."""

    path: str
    task: str
    state: State = State.UNCHECKED


def kv2_metadata_path(reference: str) -> str:
    """Swap the KV2 read prefix for the metadata one.

    KV2 splits reads and metadata across two prefixes over the same mount, so
    the path a template names is not the path an existence check calls.
    """
    return reference.replace("/data/", "/metadata/", 1)


def references(templates: list[tuple[str, str]]) -> list[SecretRef]:
    """Every distinct Vault path the given `(task, template text)` pairs ask for.

    Deduplicated on the path, keeping the first task that referenced it, so
    a path used by three tasks is one row rather than three.

    Only the extracted path string crosses this boundary. The surrounding
    template text stays here, because a jobspec template can carry a rendered
    credential.
    """
    found: dict[str, SecretRef] = {}
    for task, text in templates:
        for match in LITERAL.finditer(text):
            path = match.group("path")
            found.setdefault(path, SecretRef(path=path, task=task))
        for _ in COMPUTED.finditer(text):
            # The path is built at render time, so there is nothing to check.
            # It is surfaced as a gap in the answer rather than dropped: a
            # shrinking table is a worse lie than an incomplete one.
            key = f"<computed in {task}>"
            found.setdefault(key, SecretRef(path=key, task=task, state=State.UNKNOWN))
    return sorted(found.values(), key=lambda ref: ref.path)
