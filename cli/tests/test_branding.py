import io
from pathlib import Path

from rich.console import Console
from rich.segment import Segment

from localstack_cli.branding import HOUSE, PROMPT, WINDOW_ROWS, WORDMARK, banner, logo
from localstack_cli.status import ClusterStatus, Identity, Probe

GREEN = Probe("vault", "http://vault", True, "unsealed")
RED = Probe("nomad", "http://nomad", False, "connection refused")


def render(status: ClusterStatus, cwd: Path | None = None) -> str:
    console = Console(width=100, file=io.StringIO(), record=True)
    console.print(banner(status, cwd=cwd))
    return console.export_text()


def dot_colors(status: ClusterStatus) -> list[str]:
    """The color of each status dot, in order, read back off the render.

    Asserting on the rendered style rather than on the dataclass is the
    point: a banner that computed `ok` correctly and painted every dot the
    same color would pass any check against the status object.
    """
    console = Console(width=100, file=io.StringIO())
    segments = console.render(banner(status, cwd=Path("/tmp")))
    return [
        str(segment.style.color.name)
        for segment in segments
        if segment.text == "●" and segment.style and segment.style.color
    ]


def test_every_house_row_is_the_same_width() -> None:
    """A ragged row shears the mark once rich pads the column."""
    assert len({len(row) for row in HOUSE}) == 1


def logo_segments() -> list[Segment]:
    console = Console(width=40, file=io.StringIO())
    return list(console.render(logo()))


def test_the_house_is_painted_with_background_not_glyphs() -> None:
    """A background fill covers the whole cell; a block character covers only
    as much as the font's glyph does, and a half block covers half by
    definition. Drawing the mark in blocks makes it read as two shades of
    plum, which shows up hardest when a selection repaints the background."""
    painted = [s for s in logo_segments() if s.style and s.style.bgcolor]
    assert painted, "the house should be painted at all"
    assert all(s.text.isspace() for s in painted), (
        "a painted cell must carry no glyph, or the glyph's coverage decides "
        "how much of the cell is really coloured"
    )


def test_the_window_shows_the_terminal_background() -> None:
    """The window is a hole, not a cream fill, so the mark suits any theme."""
    prompt_line = [s for s in logo_segments() if PROMPT in s.text]
    assert prompt_line, "the prompt should be rendered"
    assert all(not (s.style and s.style.bgcolor) for s in prompt_line)


def test_the_prompt_sits_inside_the_window() -> None:
    """Inside the walls, not printed over them."""
    prompt_row = HOUSE[WINDOW_ROWS[len(WINDOW_ROWS) // 2]]
    assert PROMPT in render(ClusterStatus((), Identity(False, "x")))
    assert prompt_row.strip("# ") == ""


def test_the_roof_overhangs_the_walls() -> None:
    """The eave course spans the full width; the walls are inset from it.

    This is the detail that makes it read as the localstack house rather
    than a rectangle: the roof hangs past the body on both sides.
    """
    eave = max(HOUSE, key=lambda row: row.count("#"))
    wall_row = HOUSE[WINDOW_ROWS[0]]
    assert eave.strip() == eave, "the eave course should reach both edges"
    assert wall_row.startswith(" ") and wall_row.endswith(" ")


def test_the_banner_shows_the_wordmark_and_version() -> None:
    output = render(ClusterStatus((), Identity(False, "no token")))
    assert WORDMARK in output
    assert "localstack v" in output


def test_the_banner_lists_every_probe_with_its_detail() -> None:
    status = ClusterStatus((GREEN, RED), Identity(True, "jasper (7h30m left)"))
    output = render(status)
    for expected in ("vault", "unsealed", "nomad", "connection refused", "jasper"):
        assert expected in output


def test_a_reachable_service_gets_a_green_dot_and_a_broken_one_red() -> None:
    status = ClusterStatus((GREEN, RED), Identity(True, "jasper"))
    assert dot_colors(status) == ["green", "red", "green"]


def test_the_session_dot_is_red_when_logged_out() -> None:
    status = ClusterStatus((GREEN,), Identity(False, "no token"))
    assert dot_colors(status) == ["green", "red"]


def test_the_working_directory_is_shown_relative_to_home() -> None:
    output = render(
        ClusterStatus((), Identity(False, "no token")),
        cwd=Path.home() / "workspace",
    )
    assert "~/workspace" in output


def test_a_directory_outside_home_is_shown_in_full() -> None:
    output = render(ClusterStatus((), Identity(False, "x")), cwd=Path("/srv/thing"))
    assert "/srv/thing" in output
