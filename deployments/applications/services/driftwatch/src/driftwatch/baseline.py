"""The stored vectors every later run is compared against.

Seeded from the first successful run and kept on the job's host volume, so a
restart compares against the same reference the run before it did. Deleting
the file is how an operator says "this model is the new normal" after a
deliberate model change.

The file records the goldset's document count and the vector width alongside
the vectors. Either changing means the comparison is meaningless -- a
different corpus, or a different model -- so the reader refuses the file
instead of returning a cosine computed against the wrong thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FORMAT = "driftwatch-baseline-v1"


class BaselineMismatch(ValueError):
    """The stored baseline does not describe the goldset now being measured."""


@dataclass(frozen=True)
class Baseline:
    """Document vectors recorded at a known point in time.

    Attributes
    ----------
    vectors :
        One row per goldset document, in goldset order.
    recorded_at :
        Unix seconds when the file was written.
    """

    vectors: NDArray[np.float32]
    recorded_at: float


def read(path: Path, *, documents: int) -> Baseline | None:
    """Load the baseline at `path`, or None when there is not one yet.

    Raises
    ------
    BaselineMismatch
        If the file exists but was recorded against a different number of
        documents, or is not a baseline file at all.
    """
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as stored:
            if str(stored["format"]) != FORMAT:
                raise BaselineMismatch(f"{path} is not a {FORMAT} file")
            vectors = np.asarray(stored["vectors"], dtype=np.float32)
            recorded_at = float(stored["recorded_at"])
    except (OSError, KeyError, ValueError) as err:
        raise BaselineMismatch(f"cannot read baseline {path}: {err}") from err
    if vectors.shape[0] != documents:
        raise BaselineMismatch(
            f"baseline holds {vectors.shape[0]} documents, goldset has {documents}"
        )
    return Baseline(vectors=vectors, recorded_at=recorded_at)


def write(path: Path, vectors: NDArray[np.float32], *, now: float) -> Baseline:
    """Record `vectors` as the new baseline, replacing any file already there.

    Written to a temporary file in the same directory and renamed over the
    target, so a crash mid-write leaves the previous baseline intact rather
    than a truncated one that the next run would refuse.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    # Handed an open file rather than a name: np.savez appends `.npz` to any
    # name that lacks it, which would write beside the file the rename below
    # then looks for.
    with temporary.open("wb") as handle:
        np.savez(
            handle,
            format=np.asarray(FORMAT),
            vectors=vectors.astype(np.float32),
            recorded_at=np.asarray(now),
        )
    temporary.replace(path)
    return Baseline(vectors=vectors.astype(np.float32), recorded_at=now)
