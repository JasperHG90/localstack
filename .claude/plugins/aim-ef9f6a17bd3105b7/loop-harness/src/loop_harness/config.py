"""Per-consumer loop configuration (``.loop/config.json``).

The harness is generic; everything repo-specific is configuration the
consumer authors: the gate commands the stamp executes, where planning
tickets live, the notification title, and the review-cycle cap. A missing
file yields safe defaults with NO gates configured — the stamp refuses to
certify a tree it never tested, so an unconfigured consumer fails loudly,
never green.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from loop_harness.ledger import Stage

CONFIG_FILE = Path(".loop") / "config.json"

# A stage id names a verdict/artifact, so it must be a filesystem-safe token.
_ID_RE = re.compile(r"^[a-z0-9-]+$")

# Lifecycle anchors an action stage may run after (every stage but ``blocked``).
_ANCHOR_VALUES = frozenset(s.value for s in Stage if s is not Stage.BLOCKED)

EXAMPLE_CONFIG = {
    "gates": [
        "git add --intent-to-add -A . && uv run pytest",
        "uvx prek run --all-files",
    ],
    "plans_dir": "~/.claude/plans",
    "notify_title": "loop harness",
    "max_review_cycles": 3,
    "require_eval": False,
    "fingerprint_ignore": [],
    "review_passes": [
        {"id": "adversarial", "agent": "loop-reviewer", "enabled": True},
        {
            "id": "architectural",
            "agent": "loop-architect",
            "enabled": False,
            "baseline": "MANIFESTO.md",
        },
        {"id": "documentation", "agent": "loop-doc-reviewer", "enabled": False},
    ],
    "action_stages": [
        {
            "id": "update-documentation",
            "type": "agent",
            "ref": "loop-doc-writer",
            "after": "implementing",
            "enabled": False,
        },
        {
            "id": "report-out",
            "type": "skill",
            "ref": "your-report-skill",
            "after": "done",
            "enabled": False,
        },
    ],
}


class ConfigError(Exception):
    """A malformed or unusable loop configuration."""


@dataclass(frozen=True)
class ReviewPass:
    """One selectable review pass dispatched during the review stage.

    Each enabled pass dispatches a reviewer subagent that writes its own
    tree-bound verdict; a commit needs a passing verdict from every
    enabled pass. Passes are the mechanism behind selectable review
    (adversarial, architectural, documentation, or a consumer's own).

    Attributes
    ----------
    id : str
        Stable identity; also names the verdict file ``<slug>.<id>.md``.
    agent : str
        Name of the reviewer subagent that writes the tree-bound verdict.
    enabled : bool
        Whether this pass runs and its verdict gates the commit.
    baseline : str | None
        Optional path to a document the pass reviews against (e.g. an
        architectural baseline). Consumed by the reviewer agent, not by
        the harness.
    """

    id: str
    agent: str
    enabled: bool = True
    baseline: str | None = None

    def verdict_filename(self, slug: str) -> str:
        """Return the canonical verdict filename for this pass on ``slug``.

        The single-pass legacy path ``<slug>.md`` (used before passes
        existed) is recognized by the verdict reader as a fallback for the
        ``adversarial`` pass; it is not produced here.
        """
        return f"{slug}.{self.id}.md"


# The mandatory default: review is on, gated by an independent adversarial pass.
_DEFAULT_REVIEW_PASSES: tuple[ReviewPass, ...] = (
    ReviewPass(id="adversarial", agent="loop-reviewer"),
)


@dataclass(frozen=True)
class ActionStage:
    """One advisory action stage dispatched at a lifecycle anchor.

    Unlike a review pass, an action stage writes no verdict and does not gate
    the commit; the skill dispatches its artifact after the named anchor. Used
    for a doc-writer, a report-out step, or a consumer's own custom stage.
    Being advisory, the harness cannot prove it ran (there is no tree-bound
    artifact to check) — the skill honors it.

    Attributes
    ----------
    id : str
        Stable identity, unique across all review passes and action stages.
    kind : str
        The artifact kind to dispatch, from the JSON ``type`` key: ``"agent"``
        or ``"skill"`` (``type`` is a builtin, so the field is named ``kind``).
    ref : str
        Name of the agent or skill to dispatch, resolved from the normal
        project locations (e.g. ``.claude/agents/`` or ``.claude/skills/``).
    after : str
        The lifecycle stage after which this action runs.
    enabled : bool
        Whether the stage runs.
    """

    id: str
    kind: str
    ref: str
    after: str
    enabled: bool = True


@dataclass(frozen=True)
class LoopConfig:
    """The consumer-authored loop configuration.

    Attributes
    ----------
    gates : tuple[str, ...]
        Shell commands the stamp runs, in order; every exit code is
        recorded and all must be zero for a green stamp.
    plans_dir : str
        Where planning tickets live (informational, used by the skill).
    notify_title : str
        Title for best-effort desktop notifications.
    max_review_cycles : int
        Findings-loop cap before a ticket blocks with ``cap-exceeded``.
    review_passes : tuple[ReviewPass, ...]
        The selectable review passes; defaults to the mandatory
        adversarial pass so review is on unless deliberately opted out.
    require_review : bool
        When true (default), at least one review pass must be enabled;
        an empty or all-disabled set is a loud error. Set false to commit
        on a green stamp alone (no independent review).
    require_eval : bool
        When true, a ticket cannot enter ``implementing`` until a
        schema-valid eval marker (``.loop/evals/<slug>.md``) exists for its
        slug. Default false (off), so consumers that do not opt in see no
        behavior change.
    action_stages : tuple[ActionStage, ...]
        Advisory stages the skill dispatches at a lifecycle anchor; they
        write no verdict and never gate the commit.
    fingerprint_ignore : tuple[str, ...]
        git pathspecs (NOT ``.gitignore`` globs) that the tree fingerprint
        removes from the hashed tree, so generated working-tree files stop
        staling an otherwise-unchanged evidence stamp. It only ever
        SUBTRACTS named paths: a change to any non-ignored file still
        changes the fingerprint. Scope each pattern to a generated path:
        an over-broad pathspec (``.``, ``src``) shadows real source and
        silently defeats the whole-tree guarantee. Empty by default, so an
        absent key preserves the whole-tree behavior.
    """

    gates: tuple[str, ...] = ()
    plans_dir: str = "~/.claude/plans"
    notify_title: str = "loop harness"
    max_review_cycles: int = 3
    review_passes: tuple[ReviewPass, ...] = _DEFAULT_REVIEW_PASSES
    require_review: bool = True
    require_eval: bool = False
    action_stages: tuple[ActionStage, ...] = ()
    fingerprint_ignore: tuple[str, ...] = ()

    def enabled_review_passes(self) -> tuple[ReviewPass, ...]:
        """Return the review passes that run and whose verdicts gate the commit."""
        return tuple(p for p in self.review_passes if p.enabled)

    def enabled_action_stages(self) -> tuple[ActionStage, ...]:
        """Return the advisory action stages that run."""
        return tuple(s for s in self.action_stages if s.enabled)


def load_config(repo: Path) -> LoopConfig:
    """The consumer's config, or safe defaults when the file is absent.

    Raises
    ------
    ConfigError
        On unreadable JSON or wrong field types — a half-read config
        silently running the wrong gates would be worse than failing.
    """
    path = repo / CONFIG_FILE
    if not path.exists():
        return LoopConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw_gates = raw.get("gates", [])
        if not isinstance(raw_gates, list) or not all(isinstance(g, str) for g in raw_gates):
            raise ConfigError(
                f"'gates' in {path} must be a LIST of command strings; a bare string "
                "would char-split into nonsense gates"
            )
        gates = tuple(raw_gates)
        raw_ignore = raw.get("fingerprint_ignore", [])
        if not isinstance(raw_ignore, list) or not all(isinstance(p, str) for p in raw_ignore):
            raise ConfigError(
                f"'fingerprint_ignore' in {path} must be a LIST of git pathspec strings; "
                "a bare string would char-split into per-character patterns"
            )
        if not all(p.strip() for p in raw_ignore):
            raise ConfigError(
                f"'fingerprint_ignore' in {path} has an empty pattern; an empty git "
                "pathspec makes `git rm` fatal, which the commit hook's fail-open would "
                "swallow and silently disable the gate"
            )
        fingerprint_ignore = tuple(raw_ignore)
        review_passes = _parse_review_passes(raw, path)
        require_review = raw.get("require_review", True)
        if not isinstance(require_review, bool):
            raise ConfigError(f"'require_review' in {path} must be true or false")
        if require_review and not any(p.enabled for p in review_passes):
            raise ConfigError(
                f"no review pass is enabled in {path} but 'require_review' is true; "
                'set "require_review": false to commit on a green stamp alone'
            )
        require_eval = raw.get("require_eval", False)
        if not isinstance(require_eval, bool):
            raise ConfigError(f"'require_eval' in {path} must be true or false")
        action_stages = _parse_action_stages(raw, path, {p.id for p in review_passes})
        return LoopConfig(
            gates=gates,
            plans_dir=str(raw.get("plans_dir", LoopConfig.plans_dir)),
            notify_title=str(raw.get("notify_title", LoopConfig.notify_title)),
            max_review_cycles=int(raw.get("max_review_cycles", LoopConfig.max_review_cycles)),
            review_passes=review_passes,
            require_review=require_review,
            require_eval=require_eval,
            action_stages=action_stages,
            fingerprint_ignore=fingerprint_ignore,
        )
    except ConfigError:
        raise
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ConfigError(f"unreadable loop config at {path}: {exc}") from exc


def _parse_review_passes(raw: dict[str, object], path: Path) -> tuple[ReviewPass, ...]:
    """Parse and validate the ``review_passes`` array, or the safe default.

    A missing key synthesizes the mandatory adversarial pass (backward
    compatible with configs written before passes existed). A present key
    is strictly validated: each entry is an object with a unique kebab-case
    ``id``, a non-empty ``agent``, an optional bool ``enabled``, and an
    optional non-empty ``baseline``.

    Raises
    ------
    ConfigError
        On any malformed entry.
    """
    if "review_passes" not in raw:
        return _DEFAULT_REVIEW_PASSES
    entries = raw["review_passes"]
    if not isinstance(entries, list):
        raise ConfigError(f"'review_passes' in {path} must be a LIST of pass objects")
    passes: list[ReviewPass] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"each review pass in {path} must be an object")
        pass_id = entry.get("id")
        if not isinstance(pass_id, str) or not _ID_RE.match(pass_id):
            raise ConfigError(
                f"review pass 'id' in {path} must be a kebab-case token; got {pass_id!r}"
            )
        if pass_id in seen:
            raise ConfigError(f"duplicate review pass id '{pass_id}' in {path}")
        seen.add(pass_id)
        agent = entry.get("agent")
        if not isinstance(agent, str) or not agent:
            raise ConfigError(f"review pass '{pass_id}' in {path} needs a non-empty 'agent'")
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"review pass '{pass_id}' 'enabled' in {path} must be true or false")
        baseline = entry.get("baseline")
        if baseline is not None and (not isinstance(baseline, str) or not baseline):
            raise ConfigError(
                f"review pass '{pass_id}' 'baseline' in {path} must be a non-empty string"
            )
        passes.append(ReviewPass(id=pass_id, agent=agent, enabled=enabled, baseline=baseline))
    return tuple(passes)


def _parse_action_stages(
    raw: dict[str, object], path: Path, taken_ids: set[str]
) -> tuple[ActionStage, ...]:
    """Parse and validate the ``action_stages`` array, or an empty tuple.

    A missing key yields no action stages (backward compatible). A present key
    is strictly validated: each entry is an object with a kebab-case ``id``
    unique across ``taken_ids`` (the review-pass ids) and the other stages, a
    ``type`` of ``agent`` or ``skill``, a non-empty ``ref``, an ``after``
    naming a real lifecycle anchor, and an optional bool ``enabled``.

    Raises
    ------
    ConfigError
        On any malformed entry or an id colliding with a review pass.
    """
    if "action_stages" not in raw:
        return ()
    entries = raw["action_stages"]
    if not isinstance(entries, list):
        raise ConfigError(f"'action_stages' in {path} must be a LIST of stage objects")
    stages: list[ActionStage] = []
    seen = set(taken_ids)
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"each action stage in {path} must be an object")
        stage_id = entry.get("id")
        if not isinstance(stage_id, str) or not _ID_RE.match(stage_id):
            raise ConfigError(
                f"action stage 'id' in {path} must be a kebab-case token; got {stage_id!r}"
            )
        if stage_id in seen:
            raise ConfigError(
                f"duplicate stage id '{stage_id}' in {path} "
                "(ids must be unique across review_passes and action_stages)"
            )
        seen.add(stage_id)
        kind = entry.get("type")
        if kind not in ("agent", "skill"):
            raise ConfigError(
                f"action stage '{stage_id}' 'type' in {path} must be 'agent' or 'skill'"
            )
        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ConfigError(f"action stage '{stage_id}' in {path} needs a non-empty 'ref'")
        after = entry.get("after")
        if after not in _ANCHOR_VALUES:
            raise ConfigError(
                f"action stage '{stage_id}' 'after' in {path} must be a lifecycle anchor "
                f"(one of {sorted(_ANCHOR_VALUES)})"
            )
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(
                f"action stage '{stage_id}' 'enabled' in {path} must be true or false"
            )
        stages.append(ActionStage(id=stage_id, kind=kind, ref=ref, after=after, enabled=enabled))
    return tuple(stages)


def write_example_config(repo: Path) -> Path:
    """Scaffold ``.loop/config.json`` with the documented example values.

    Refuses to overwrite an existing config.

    Raises
    ------
    ConfigError
        If a config already exists.
    """
    path = repo / CONFIG_FILE
    if path.exists():
        raise ConfigError(f"{path} already exists; edit it instead")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(EXAMPLE_CONFIG, indent=2) + "\n", encoding="utf-8")
    return path
