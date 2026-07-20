"""Config: consumer-authored gates, safe defaults, loud failures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop_harness.config import (
    CONFIG_FILE,
    ActionStage,
    ConfigError,
    LoopConfig,
    ReviewPass,
    load_config,
    write_example_config,
)
from loop_harness.stamp import run_gates


def _write(repo: Path, payload: dict[str, object]) -> None:
    """Write a ``.loop/config.json`` under ``repo`` for a test."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_config_yields_safe_defaults(repo: Path) -> None:
    """No file means defaults with ZERO gates configured."""
    config = load_config(repo)
    assert config.gates == ()
    assert config.max_review_cycles == 3


def test_config_round_trip(repo: Path) -> None:
    """Authored values load exactly."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "gates": ["true", "echo ok"],
                "plans_dir": "./tickets",
                "notify_title": "my loop",
                "max_review_cycles": 5,
            }
        ),
        encoding="utf-8",
    )
    config = load_config(repo)
    assert config.gates == ("true", "echo ok")
    assert config.plans_dir == "./tickets"
    assert config.notify_title == "my loop"
    assert config.max_review_cycles == 5


def test_malformed_config_raises(repo: Path) -> None:
    """A half-read config running the wrong gates would be worse than failing."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(repo)


def test_example_scaffold_refuses_overwrite(repo: Path) -> None:
    """`loopctl init` writes once and never clobbers an authored config."""
    path = write_example_config(repo)
    assert load_config(repo).gates  # the example carries real gate commands
    with pytest.raises(ConfigError):
        write_example_config(repo)
    assert path.exists()


def test_run_gates_records_every_exit_code(repo: Path) -> None:
    """All gates run even after a failure; every exit code is recorded."""
    results = run_gates(repo, LoopConfig(gates=("true", "false", "true")))
    assert [r.exit_code for r in results] == [0, 1, 0]
    assert results[1].command == "false"


def test_run_gates_refuses_empty_gate_list(repo: Path) -> None:
    """An unconfigured consumer must never stamp green."""
    with pytest.raises(ValueError, match="no gates configured"):
        run_gates(repo, LoopConfig())


def test_bare_string_gates_raise(repo: Path) -> None:
    """The likeliest authoring mistake: a bare string would char-split into
    nonsense gates; the loader must reject it, per its contract."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gates": "uv run pytest"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="LIST"):
        load_config(repo)


def test_non_string_gate_elements_raise(repo: Path) -> None:
    """Gate elements must be command strings, never coerced from other types."""
    path = repo / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gates": ["true", 123]}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(repo)


def test_review_passes_round_trip(repo: Path) -> None:
    """Authored review passes load exactly, and enabled ones are filtered."""
    _write(
        repo,
        {
            "gates": ["true"],
            "review_passes": [
                {"id": "adversarial", "agent": "loop-reviewer"},
                {
                    "id": "architectural",
                    "agent": "loop-architect",
                    "enabled": False,
                    "baseline": "MANIFESTO.md",
                },
            ],
        },
    )
    config = load_config(repo)
    assert config.review_passes == (
        ReviewPass(id="adversarial", agent="loop-reviewer"),
        ReviewPass(
            id="architectural", agent="loop-architect", enabled=False, baseline="MANIFESTO.md"
        ),
    )
    assert config.enabled_review_passes() == (ReviewPass(id="adversarial", agent="loop-reviewer"),)


def test_review_pass_verdict_filename() -> None:
    """The verdict file is namespaced per pass id."""
    assert ReviewPass(id="architectural", agent="a").verdict_filename("my-slug") == (
        "my-slug.architectural.md"
    )


def test_absent_review_passes_synthesizes_adversarial(repo: Path) -> None:
    """A config with no review_passes key still requires the adversarial pass."""
    _write(repo, {"gates": ["true"]})
    assert load_config(repo).enabled_review_passes() == (
        ReviewPass(id="adversarial", agent="loop-reviewer"),
    )


def test_missing_config_keeps_review_on(repo: Path) -> None:
    """No config file at all still defaults to the mandatory adversarial pass."""
    assert load_config(repo).enabled_review_passes() == (
        ReviewPass(id="adversarial", agent="loop-reviewer"),
    )


def test_empty_review_passes_needs_explicit_opt_out(repo: Path) -> None:
    """An empty list must fail loud, not silently disable all review."""
    _write(repo, {"gates": ["true"], "review_passes": []})
    with pytest.raises(ConfigError, match="require_review"):
        load_config(repo)


def test_all_disabled_review_passes_needs_explicit_opt_out(repo: Path) -> None:
    """All-disabled is the same accidental cliff as an empty list."""
    _write(
        repo,
        {
            "gates": ["true"],
            "review_passes": [{"id": "adversarial", "agent": "loop-reviewer", "enabled": False}],
        },
    )
    with pytest.raises(ConfigError, match="require_review"):
        load_config(repo)


def test_review_disabled_with_explicit_opt_out(repo: Path) -> None:
    """Stamp-only commits require a deliberate require_review:false."""
    _write(repo, {"gates": ["true"], "require_review": False, "review_passes": []})
    config = load_config(repo)
    assert config.require_review is False
    assert config.enabled_review_passes() == ()


def test_duplicate_review_pass_id_raises(repo: Path) -> None:
    """Two passes with the same id would collide on their verdict file."""
    _write(
        repo,
        {
            "gates": ["true"],
            "review_passes": [
                {"id": "adversarial", "agent": "loop-reviewer"},
                {"id": "adversarial", "agent": "other"},
            ],
        },
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(repo)


def test_malformed_review_pass_id_raises(repo: Path) -> None:
    """Ids name a verdict file, so they must be kebab-case tokens."""
    _write(
        repo,
        {"gates": ["true"], "review_passes": [{"id": "Bad Id", "agent": "loop-reviewer"}]},
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_review_pass_missing_agent_raises(repo: Path) -> None:
    """A pass with no reviewer agent cannot be dispatched."""
    _write(repo, {"gates": ["true"], "review_passes": [{"id": "adversarial"}]})
    with pytest.raises(ConfigError):
        load_config(repo)


def test_review_pass_empty_baseline_raises(repo: Path) -> None:
    """A present-but-empty baseline is an authoring mistake, not 'no baseline'."""
    _write(
        repo,
        {
            "gates": ["true"],
            "review_passes": [
                {"id": "adversarial", "agent": "loop-reviewer"},
                {"id": "architectural", "agent": "loop-architect", "baseline": ""},
            ],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_review_passes_bare_value_raises(repo: Path) -> None:
    """review_passes must be a list of objects, never a bare string."""
    _write(repo, {"gates": ["true"], "review_passes": "adversarial"})
    with pytest.raises(ConfigError):
        load_config(repo)


def test_require_review_non_bool_raises(repo: Path) -> None:
    """require_review is a flag; a non-bool is a config error."""
    _write(repo, {"gates": ["true"], "require_review": "yes"})
    with pytest.raises(ConfigError):
        load_config(repo)


def test_example_config_carries_enabled_adversarial(repo: Path) -> None:
    """The scaffolded config ships review on (adversarial), extras opt-in."""
    write_example_config(repo)
    config = load_config(repo)
    ids = [p.id for p in config.review_passes]
    assert "adversarial" in ids
    assert config.enabled_review_passes()  # adversarial is enabled by default


def test_action_stages_round_trip(repo: Path) -> None:
    """Authored action stages load exactly, and enabled ones are filtered."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [
                {
                    "id": "update-documentation",
                    "type": "agent",
                    "ref": "loop-doc-writer",
                    "after": "implementing",
                },
                {
                    "id": "report-out",
                    "type": "skill",
                    "ref": "my-report",
                    "after": "done",
                    "enabled": False,
                },
            ],
        },
    )
    config = load_config(repo)
    assert config.action_stages == (
        ActionStage(
            id="update-documentation", kind="agent", ref="loop-doc-writer", after="implementing"
        ),
        ActionStage(id="report-out", kind="skill", ref="my-report", after="done", enabled=False),
    )
    assert config.enabled_action_stages() == (
        ActionStage(
            id="update-documentation", kind="agent", ref="loop-doc-writer", after="implementing"
        ),
    )


def test_absent_action_stages_is_empty(repo: Path) -> None:
    """A config with no action_stages key yields an empty tuple (backward compat)."""
    _write(repo, {"gates": ["true"]})
    assert load_config(repo).action_stages == ()


def test_action_stage_bad_type_raises(repo: Path) -> None:
    """The dispatch kind must be agent or skill."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [{"id": "x", "type": "hook", "ref": "r", "after": "done"}],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_action_stage_empty_ref_raises(repo: Path) -> None:
    """A stage with no artifact to dispatch is a config error."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [{"id": "x", "type": "agent", "ref": "", "after": "done"}],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_action_stage_bad_anchor_raises(repo: Path) -> None:
    """`after` must name a real lifecycle stage."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [{"id": "x", "type": "agent", "ref": "r", "after": "nowhere"}],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_action_stage_duplicate_id_raises(repo: Path) -> None:
    """Two action stages cannot share an id."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [
                {"id": "x", "type": "agent", "ref": "a", "after": "done"},
                {"id": "x", "type": "skill", "ref": "b", "after": "done"},
            ],
        },
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(repo)


def test_action_stage_id_colliding_with_review_pass_raises(repo: Path) -> None:
    """Stage ids are globally unique across review passes and action stages."""
    _write(
        repo,
        {
            "gates": ["true"],
            "review_passes": [{"id": "adversarial", "agent": "loop-reviewer"}],
            "action_stages": [{"id": "adversarial", "type": "agent", "ref": "r", "after": "done"}],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_action_stage_not_a_list_raises(repo: Path) -> None:
    """action_stages must be a list of objects."""
    _write(repo, {"gates": ["true"], "action_stages": "update-documentation"})
    with pytest.raises(ConfigError):
        load_config(repo)


def test_action_stage_non_bool_enabled_raises(repo: Path) -> None:
    """`enabled` is a flag; a non-bool is a config error."""
    _write(
        repo,
        {
            "gates": ["true"],
            "action_stages": [
                {"id": "x", "type": "agent", "ref": "r", "after": "done", "enabled": "yes"}
            ],
        },
    )
    with pytest.raises(ConfigError):
        load_config(repo)


def test_example_config_carries_action_stages(repo: Path) -> None:
    """The scaffolded config ships an update-documentation action stage, opt-in."""
    write_example_config(repo)
    config = load_config(repo)
    ids = {s.id for s in config.action_stages}
    assert "update-documentation" in ids
    assert config.enabled_action_stages() == ()  # extras ship disabled
