"""Lifecycle state machine: mechanical entry criteria per stage transition.

Stages: ready -> implementing -> gates -> self-review -> adversarial-review
-> commit -> done. Findings loop adversarial-review -> gates (capped).
``blocked`` is reachable from anywhere and returns only to ``ready``.

Evidence, not claims: entering ``gates`` needs a fresh (tree-matching)
stamp; ``self-review`` and ``adversarial-review`` need a GREEN stamp;
``commit`` additionally needs every enabled review pass's verdict bound to
the exact tree (nothing extra when review is deliberately disabled).
"""

from __future__ import annotations

from collections.abc import Sequence

from loop_harness.ledger import Stage
from loop_harness.stamp import StampStatus, StampVerdict

MAX_REVIEW_CYCLES = 3

_ORDER = [
    Stage.READY,
    Stage.IMPLEMENTING,
    Stage.GATES,
    Stage.SELF_REVIEW,
    Stage.ADVERSARIAL_REVIEW,
    Stage.COMMIT,
    Stage.DONE,
]
_FRESH = frozenset({StampStatus.OK, StampStatus.RED})


class LifecycleError(Exception):
    """A stage transition whose entry criteria are not met."""


def validate_transition(
    current: Stage,
    target: Stage,
    *,
    stamp: StampVerdict | None = None,
    pass_verdict_trees: Sequence[tuple[str, str | None]] = (),
    current_tree: str | None = None,
    review_cycles: int = 0,
    max_review_cycles: int = MAX_REVIEW_CYCLES,
) -> None:
    """Raise ``LifecycleError`` unless ``current -> target`` is permitted.

    Parameters
    ----------
    pass_verdict_trees :
        For a ``commit`` target, one ``(pass_id, tree)`` pair per ENABLED
        review pass, where ``tree`` is the fingerprint bound by that pass's
        passing verdict (or ``None`` when absent/failing). Every pair must
        match ``current_tree``. An empty sequence means review is disabled,
        so a green stamp alone authorizes the commit. Ignored for every
        other target.
    current_tree :
        Fingerprint of the tree being committed, checked against each pass.
    """
    if target is Stage.BLOCKED:
        return  # always reachable; the blocker code is recorded on the entry
    if current is Stage.BLOCKED:
        if target is Stage.READY:
            return  # operator unblocked the ticket
        raise LifecycleError("a blocked ticket returns to ready, nothing else")
    if current is Stage.ADVERSARIAL_REVIEW and target is Stage.GATES:
        if review_cycles >= max_review_cycles:
            raise LifecycleError(
                f"review-cycle cap ({max_review_cycles}) reached: block with cap-exceeded"
            )
        return  # findings loop back to gates
    if _ORDER.index(target) != _ORDER.index(current) + 1:
        raise LifecycleError(f"cannot jump {current.value} -> {target.value}")

    if target is Stage.GATES:
        if stamp is None or stamp.status not in _FRESH:
            detail = stamp.status.value if stamp is not None else "absent"
            raise LifecycleError(f"gates entry needs a fresh stamp (got: {detail})")
    elif target in (Stage.SELF_REVIEW, Stage.ADVERSARIAL_REVIEW):
        if stamp is None or not stamp.ok:
            detail = stamp.status.value if stamp is not None else "absent"
            raise LifecycleError(f"{target.value} entry needs a green stamp (got: {detail})")
    elif target is Stage.COMMIT:
        if stamp is None or not stamp.ok:
            raise LifecycleError("commit entry needs a green stamp")
        for pass_id, verdict_tree in pass_verdict_trees:
            if verdict_tree is None or current_tree is None or verdict_tree != current_tree:
                raise LifecycleError(
                    f"commit entry needs review pass '{pass_id}' verdict "
                    "bound to the exact current tree"
                )
