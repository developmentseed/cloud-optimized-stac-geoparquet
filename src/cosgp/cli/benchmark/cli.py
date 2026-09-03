from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from typer import Argument, BadParameter, Option, Typer

from .compare import (
    RunLoadError,
    compare,
    load_run,
    print_comparison,
    write_csv,
    write_markdown,
)
from .queries import DEFAULT_REPEATS

benchmark_app = Typer(help="Benchmark datasets and compare the results.")


@benchmark_app.command("run")
def run(
    name: Annotated[
        str,
        Argument(help="Short label for the dataset, used in the output directory name"),
    ],
    path: Annotated[
        str,
        Argument(
            help="Glob or URI to the stac-geoparquet dataset, passed to DuckDB's read_parquet"
        ),
    ],
    out_dir: Annotated[
        Path, Option(help="Directory to write the run's results into")
    ] = Path("benchmark-results"),
    repeats: Annotated[
        int, Option(help="Number of times to repeat each query for timing")
    ] = DEFAULT_REPEATS,
    progress: Annotated[
        bool,
        Option(
            help="Show a progress bar. If disabled, progress is logged at INFO level instead."
        ),
    ] = True,
) -> None:
    """Runs benchmarks for a single dataset."""
    try:
        from .runner import BenchmarkRunner
    except ImportError as e:
        raise BadParameter(
            "duckdb is required for `cosgp benchmark run`; "
            "install with `pip install cosgp[benchmark]` (or `uv sync --extra benchmark`)"
        ) from e
    if not progress:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_file = BenchmarkRunner(repeats=repeats, progress=progress).run(
        name, path, out_dir
    )
    print(f"wrote {run_file}")


@benchmark_app.command("compare")
def compare_command(
    run_a: Annotated[
        Path, Argument(help="Path to the first run's directory or run.json file")
    ],
    run_b: Annotated[
        Path, Argument(help="Path to the second run's directory or run.json file")
    ],
    outfile: Annotated[
        Path | None,
        Option(
            help="Optional file to also write the comparison to, as markdown (.md) or CSV (.csv)"
        ),
    ] = None,
) -> None:
    """Compares benchmarks for two datasets."""
    try:
        a = load_run(run_a)
        b = load_run(run_b)
    except RunLoadError as e:
        raise BadParameter(str(e)) from e
    rows, skipped = compare(a, b)
    print_comparison(a, b, rows, skipped)
    if outfile is not None:
        if outfile.suffix == ".md":
            write_markdown(a, b, rows, outfile)
        elif outfile.suffix == ".csv":
            write_csv(a, b, rows, outfile)
        else:
            raise BadParameter(
                f"unsupported outfile extension: {outfile.suffix!r} (expected .md or .csv)"
            )
