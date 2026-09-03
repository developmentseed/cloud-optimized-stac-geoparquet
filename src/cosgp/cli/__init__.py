from __future__ import annotations

from typer import Typer

from .convert import convert
from .info import info

app = Typer()

app.command()(convert)
app.command(name="create")(convert)
app.command()(info)
