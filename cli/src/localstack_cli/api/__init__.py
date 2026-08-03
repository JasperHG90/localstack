"""Read-only cluster fetchers, shared by every renderer.

The contract this package keeps, so more than one front end can use it:
dataclasses out, never rendered strings; no `typer`, no `rich`, no Textual
imported here; addresses come from `config.py` and never appear as literals.

`monitor` (the Textual panel) is the first consumer. `status` and the other
one-shot commands are the second. Two fetch layers would mean two places
that decide what a 403 means, and they would disagree.
"""
