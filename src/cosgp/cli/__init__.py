from __future__ import annotations

from typer import Typer

from .benchmark.cli import benchmark_app
from .convert import convert
from .info import info

app = Typer()

app.command()(convert)
app.command()(info)
app.add_typer(benchmark_app, name="benchmark")
