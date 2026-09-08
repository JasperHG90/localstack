from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from driftwatch import baseline


def test_a_missing_baseline_is_none_not_an_error(tmp_path: Path) -> None:
    assert baseline.read(tmp_path / "absent.npz", documents=3) is None


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "baseline.npz"
    vectors = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    baseline.write(path, vectors, now=1000.0)
    stored = baseline.read(path, documents=2)

    assert stored is not None
    assert np.allclose(stored.vectors, vectors)
    assert stored.recorded_at == 1000.0


def test_write_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "baseline.npz"

    baseline.write(path, np.zeros((2, 2), dtype=np.float32), now=1.0)

    assert [item.name for item in tmp_path.iterdir()] == ["baseline.npz"]


def test_a_second_write_replaces_the_first(tmp_path: Path) -> None:
    path = tmp_path / "baseline.npz"
    baseline.write(path, np.ones((2, 2), dtype=np.float32), now=1.0)

    baseline.write(path, np.zeros((2, 2), dtype=np.float32), now=2.0)
    stored = baseline.read(path, documents=2)

    assert stored is not None
    assert np.allclose(stored.vectors, 0.0)
    assert stored.recorded_at == 2.0


def test_a_different_document_count_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "baseline.npz"
    baseline.write(path, np.zeros((2, 4), dtype=np.float32), now=1.0)

    with pytest.raises(baseline.BaselineMismatch, match="holds 2 documents"):
        baseline.read(path, documents=3)


def test_a_file_that_is_not_a_baseline_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "baseline.npz"
    path.write_bytes(b"not an npz")

    with pytest.raises(baseline.BaselineMismatch, match="cannot read baseline"):
        baseline.read(path, documents=2)


def test_the_parent_directory_is_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "baseline.npz"

    baseline.write(path, np.zeros((1, 2), dtype=np.float32), now=1.0)

    assert path.exists()
