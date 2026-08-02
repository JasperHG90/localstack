"""The banner: the localstack mark, the build line and the cluster status.

Kept apart from `main` so the layout can be tested by rendering it to a
string, without going through the CLI.
"""

import platform
import sys
from importlib.metadata import version
from pathlib import Path

from rich.console import Console, Group, RenderableType
from rich.table import Table
from rich.text import Text

from localstack_cli.status import ClusterStatus

# Sampled from `assets/logos/localstack-logo.png`. BRAND_PLUM is the logo's
# own plum, too dark to read on a dark terminal, so it is kept as the brand
# fact and MARK is the lifted tint actually painted. The window is left as
# terminal background, so the mark sits on whatever theme the user runs.
BRAND_PLUM = "#592742"
MARK = "#a34c76"

DIM = "grey58"

# A mask, not the glyphs: `#` is a house cell and a space is empty. The mark
# is painted with BACKGROUND colour on spaces rather than drawn with block
# characters. A background fill always covers the whole cell; `█` covers only
# as much of it as the font's glyph does, and `▄` covers half by definition,
# so a mark drawn in block characters shows seams and reads as two shades of
# plum. It is most obvious when a selection or hover repaints the background
# underneath. Rows must stay the same width; a ragged row shears the mark
# when rich pads the column.
HOUSE = (
    "       ###       ",
    "     #######     ",
    "   ###########   ",
    " ############### ",
    "#################",
    "  ##         ##  ",
    "  ##         ##  ",
    "  ##         ##  ",
    "  #############  ",
)

# The window cut into the walls: rows 5 to 7, columns 4 to 12 inclusive.
WINDOW_ROWS = range(5, 8)
WINDOW_COLS = range(4, 13)
PROMPT = ">_"

WORDMARK = "LOCALSTACK"


def _runs(row: str, cell: str) -> list[tuple[int, int]]:
    """The (start, stop) spans of `cell` in a mask row."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, char in enumerate(row + " "):
        if char == cell and start is None:
            start = index
        elif char != cell and start is not None:
            spans.append((start, index))
            start = None
    return spans


def logo() -> Text:
    """The house, painted as coloured cells rather than drawn in glyphs."""
    prompt_row = WINDOW_ROWS[len(WINDOW_ROWS) // 2]
    lines = []
    for y, mask in enumerate(HOUSE):
        text = list(" " * len(mask))
        if y == prompt_row:
            at = WINDOW_COLS.start + 2
            text[at : at + len(PROMPT)] = PROMPT
        line = Text("".join(text), style=MARK)
        for start, stop in _runs(mask, "#"):
            line.stylize(f"on {MARK}", start, stop)
        lines.append(line)
    return Text("\n").join(lines)


def _home_relative(path: Path) -> str:
    """`~/workspace` reads better than a full path and leaks less."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


def _status_rows(status: ClusterStatus) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(width=1)
    table.add_column(min_width=7)
    table.add_column()
    for probe in status.probes:
        table.add_row(
            Text("●", style="green" if probe.ok else "red"),
            Text(probe.name, style=DIM),
            Text(probe.detail, style=DIM),
        )
    identity = status.identity
    table.add_row(
        Text("●", style="green" if identity.logged_in else "red"),
        Text("session", style=DIM),
        Text(identity.detail, style=DIM),
    )
    return table


def banner(status: ClusterStatus, cwd: Path | None = None) -> RenderableType:
    """The mark on the left, the build line and status on the right."""
    where = cwd if cwd is not None else Path.cwd()
    details = Group(
        Text(WORDMARK, style=f"bold {MARK}"),
        Text(f"localstack v{version('localstack-cli')}", style=DIM),
        Text(
            f"Python {platform.python_version()} · {platform.system()}",
            style=DIM,
        ),
        Text(_home_relative(where), style=DIM),
        Text(""),
        _status_rows(status),
    )
    layout = Table.grid(padding=(0, 3))
    layout.add_column()
    layout.add_column()
    layout.add_row(logo(), details)
    return layout


def print_banner(status: ClusterStatus, console: Console | None = None) -> None:
    # Banner chrome goes to stderr so `localstack <cmd> | jq` stays clean once
    # the read commands land. Help itself still goes to stdout, via click.
    target = console if console is not None else Console(file=sys.stderr)
    target.print()
    target.print(banner(status))
    target.print()
