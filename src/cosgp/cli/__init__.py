from __future__ import annotations

from typer import Typer

from .convert import convert

app = Typer()

app.command()(convert)
app.command(name="create")(convert)
