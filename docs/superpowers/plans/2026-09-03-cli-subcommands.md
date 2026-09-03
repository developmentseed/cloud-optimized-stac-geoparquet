# CLI Subcommand Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `cosgp` from a single-command CLI into a multi-subcommand CLI with `convert` (aliased `create`), `info`, and `benchmark` subcommands sharing common setup/config logic.

**Architecture:** `src/cosgp/cli.py` becomes a `src/cosgp/cli/` package. Shared glob-resolution and logging-setup helpers move to `cli/common.py`. Each subcommand is a plain function in its own module, registered onto a single root `Typer` app in `cli/__init__.py`. The `benchmark` subcommand is ported from the `rework-benchmarking` branch's already-working DuckDB implementation into `cli/benchmark/`, wired in as a nested `Typer` sub-app instead of the separate `cosgp-benchmark` script it shipped as there.

**Tech Stack:** Python 3.12, Typer, PyArrow, DuckDB (optional extra), Rich.

**Spec:** `docs/superpowers/specs/2026-09-03-cli-subcommands-design.md`

## Global Constraints

- No automated tests are added or ported in this work (explicit user instruction). Verification is manual CLI smoke-testing, plus confirming the existing test suite and lint/type-check still pass.
- `duckdb`/`pytz` stay an optional `benchmark` extra (`pyproject.toml` `[project.optional-dependencies]`), not a base dependency.
- `runner.py` (conversion `Runner`) and `progress.py` are unchanged and stay at `src/cosgp/`.
- `convert` and `create` must invoke the exact same underlying function (one implementation, two registered names) — no duplicated docstring/logic.

---

### Task 1: Restructure `cli.py` into a package with shared helpers and the `convert`/`create` command

**Files:**
- Create: `src/cosgp/cli/__init__.py`
- Create: `src/cosgp/cli/common.py`
- Create: `src/cosgp/cli/convert.py`
- Delete: `src/cosgp/cli.py`

**Interfaces:**
- Consumes: `cosgp.runner.Runner`, `cosgp.runner.DEFAULT_BUCKET_SIZE`, `cosgp.runner.BBox` (existing, unchanged).
- Produces:
  - `cosgp.cli.common.Datetime` — `.parse(value: str) -> Datetime` classmethod parser, instances have `.start: datetime.datetime` / `.end: datetime.datetime`.
  - `cosgp.cli.common.resolve_infiles(infile: Path, pattern: str = "*.parquet") -> list[Path]`
  - `cosgp.cli.common.configure_logging(progress: bool) -> None`
  - `cosgp.cli.convert.convert(...) -> None` (Typer command callback)
  - `cosgp.cli.app: Typer` (the root app, importable as `cosgp.cli:app` for `[project.scripts]`)

- [ ] **Step 1: Create `src/cosgp/cli/common.py`**

```python
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path


class Datetime:
    @classmethod
    def parse(cls, value: str) -> Datetime:
        parts = value.split("/")
        if len(parts) == 2:
            raise NotImplementedError
        elif len(parts) == 1:
            sub_parts = parts[0].split("-")
            if len(sub_parts) == 1:
                return Datetime.year(int(sub_parts[0]))
            elif len(sub_parts) == 2:
                return Datetime.month(int(sub_parts[0]), int(sub_parts[1]))
            elif len(sub_parts) == 3:
                return Datetime.day(
                    int(sub_parts[0]), int(sub_parts[1]), int(sub_parts[2])
                )
            else:
                raise ValueError(f"invalid datetime: {value}")
        else:
            raise ValueError(f"invalid datetime: {value}")

    @classmethod
    def year(cls, year: int) -> Datetime:
        start = dt.date(year, 1, 1)
        end = dt.date(year + 1, 1, 1)
        return Datetime(
            dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC),
            dt.datetime.combine(end, dt.time.min, tzinfo=dt.UTC),
        )

    @classmethod
    def month(cls, year: int, month: int) -> Datetime:
        start = dt.date(year, month, 1)
        end = dt.date(year, month + 1, 1)
        return Datetime(
            dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC),
            dt.datetime.combine(end, dt.time.min, tzinfo=dt.UTC),
        )

    @classmethod
    def day(cls, year: int, month: int, day: int) -> Datetime:
        start = dt.date(year, month, day)
        end = dt.date(year, month, day + 1)
        return Datetime(
            dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC),
            dt.datetime.combine(end, dt.time.min, tzinfo=dt.UTC),
        )

    def __init__(self, start: dt.datetime, end: dt.datetime):
        self.start = start
        self.end = end


def resolve_infiles(infile: Path, pattern: str = "*.parquet") -> list[Path]:
    """Resolves a file-or-directory argument into a sorted list of parquet files."""
    infiles = [infile] if infile.is_file() else sorted(infile.glob(pattern))
    if not infiles:
        raise ValueError(f"no parquet files in {infile}")
    return infiles


def configure_logging(progress: bool) -> None:
    if not progress:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
```

This is a verbatim move of the `Datetime` class out of the current `src/cosgp/cli.py`, plus the glob logic and logging-setup idiom extracted out of the current `create()` function into standalone helpers.

- [ ] **Step 2: Create `src/cosgp/cli/convert.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from typer import Argument, Option

from ..runner import DEFAULT_BUCKET_SIZE, BBox, Runner
from .common import Datetime, configure_logging, resolve_infiles


def convert(
    infile: Annotated[
        Path,
        Argument(
            help="The input stac-geoparquet file, or directory holding stac-geoparquet files (these files must have a .parquet suffix)"
        ),
    ],
    datetime: Annotated[
        Datetime,
        Argument(
            parser=Datetime.parse,
            help="The datetime range to use for the hash bounds. Can be specified as a start/end interval or via a simple year, a year-month, or a year-month-day",
        ),
    ],
    outdir: Annotated[
        Path,
        Argument(
            help="The output directory for the cloud-optimized stac-geoparquet files"
        ),
    ],
    bbox: Annotated[
        BBox | None,
        Option(
            help="The bounding box to use for the hash bounds. If not provided, defaults to the global bbox"
        ),
    ] = None,
    prefix_id: Annotated[
        bool,
        Option(
            help="Prefix the ids of each item with their hash value, greatly speeding up search-by-id queries. Might not be necessary if the item ids are already prefixed with datetimes in YMD format."
        ),
    ] = False,
    temporary_directory: Annotated[
        Path | None,
        Option(
            help="The temporary directory to use for intermediate files. If None, the system default will be used"
        ),
    ] = None,
    bucket_size: Annotated[
        int,
        Option(
            help="Target uncompressed size, in bytes, for each sorted output file. The number of hash buckets is estimated from the total input data volume so that each bucket is roughly this size."
        ),
    ] = DEFAULT_BUCKET_SIZE,
    match_file_count: Annotated[
        bool,
        Option(
            help="Produce the same number of output files as input files instead of sizing them by bucket-size. Useful for testing the effects of sorting in isolation from resizing. Overrides bucket-size."
        ),
    ] = False,
    progress: Annotated[
        bool,
        Option(
            help="Show a progress bar. If disabled, progress is logged at INFO level instead."
        ),
    ] = True,
) -> None:
    """Creates one or more cloud-optimized stac-geoparquet files.

    This is a three-step process:

        1. Copy each item to new stac-geoparquet files, adding a stac-hash and (optionally) prefixing the id with that hash
        2. Stage each item into "bucketed" datasets, partitioned by hash value
        3. Internally sort each partitioned dataset, then write the output files
    """
    configure_logging(progress)
    infiles = resolve_infiles(infile)
    outdir.mkdir(parents=True, exist_ok=True)
    Runner(
        temporary_directory=temporary_directory,
        bucket_size=bucket_size,
        progress=progress,
        prefix_id=prefix_id,
        match_file_count=match_file_count,
    ).run(
        infiles=infiles,
        start_datetime=datetime.start,
        end_datetime=datetime.end,
        bbox=bbox,
        outdir=outdir,
    )
```

This is the current `create()` body from `src/cosgp/cli.py`, renamed to `convert`, with the inline glob/logging logic replaced by the Step 1 helpers.

- [ ] **Step 3: Create `src/cosgp/cli/__init__.py`**

```python
from __future__ import annotations

from typer import Typer

from .convert import convert

app = Typer()

app.command()(convert)
app.command(name="create")(convert)
```

(The `benchmark` and `info` registrations are added in later tasks — this step alone must leave `convert`/`create` fully working.)

- [ ] **Step 4: Delete the old single-file module**

```bash
rm src/cosgp/cli.py
```

- [ ] **Step 5: Verify the package resolves and both command names work**

Run:

```bash
uv sync
uv run cosgp --help
uv run cosgp convert --help
uv run cosgp create --help
```

Expected: `--help` lists `convert` and `create`; both `--help` outputs show the identical three-step docstring and full option list.

- [ ] **Step 6: Smoke-test an actual conversion through both names**

```bash
mkdir -p /tmp/cosgp-smoke
uv run python - <<'PY'
import pyarrow
import pyarrow.parquet as pq

schema = pyarrow.schema([
    pyarrow.field("id", pyarrow.string()),
    pyarrow.field("datetime", pyarrow.timestamp("us", tz="UTC")),
    pyarrow.field("bbox", pyarrow.struct([
        pyarrow.field("xmin", pyarrow.float64()),
        pyarrow.field("ymin", pyarrow.float64()),
        pyarrow.field("xmax", pyarrow.float64()),
        pyarrow.field("ymax", pyarrow.float64()),
    ])),
])
table = pyarrow.table(
    {
        "id": [f"item-{i}" for i in range(50)],
        "datetime": pyarrow.array(
            [1_700_000_000 + i for i in range(50)], pyarrow.timestamp("us", tz="UTC")
        ),
        "bbox": [
            {"xmin": -10.0, "ymin": -10.0, "xmax": 10.0, "ymax": 10.0}
            for _ in range(50)
        ],
    },
    schema=schema,
)
pq.write_table(table, "/tmp/cosgp-smoke/in.parquet")
PY

uv run cosgp convert /tmp/cosgp-smoke/in.parquet 2024 /tmp/cosgp-smoke/out --no-progress
uv run cosgp create /tmp/cosgp-smoke/in.parquet 2024 /tmp/cosgp-smoke/out2 --no-progress
ls /tmp/cosgp-smoke/out /tmp/cosgp-smoke/out2
```

Expected: both `out` and `out2` contain identical-looking `part-*.parquet` output files (both commands ran the same underlying logic).

- [ ] **Step 7: Confirm the existing test suite still passes**

Run: `uv run pytest`
Expected: PASS (unchanged — `tests/test_runner.py` only imports `cosgp.runner`, which was not touched).

- [ ] **Step 8: Commit**

```bash
git add src/cosgp/cli.py src/cosgp/cli/
git commit -m "refactor: restructure cli.py into a cli package with shared helpers"
```

---

### Task 2: Add the `info` subcommand

**Files:**
- Create: `src/cosgp/cli/info.py`
- Modify: `src/cosgp/cli/__init__.py`

**Interfaces:**
- Consumes: `cosgp.cli.common.resolve_infiles` (from Task 1).
- Produces:
  - `cosgp.cli.info.FileInfo` — frozen dataclass with fields `file: str`, `rows: int`, `row_groups: int`, `size_bytes: int`, `has_hash_columns: bool`, `sorted_by_hash: bool`, `prefixed_id: bool`, `cloud_optimized: bool`.
  - `cosgp.cli.info.file_info(path: Path) -> FileInfo`
  - `cosgp.cli.info.info(...) -> None` (Typer command callback)

- [ ] **Step 1: Create `src/cosgp/cli/info.py`**

```python
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated

from pyarrow.parquet import ParquetFile
from rich.console import Console
from rich.table import Table
from typer import Argument, Option

from .common import resolve_infiles

REQUIRED_HASH_COLUMNS = ("hash:hash", "hash:start_datetime", "hash:end_datetime")
PREFIXED_ID_PATTERN = re.compile(r"^[0-9a-f]{16}-")


@dataclass(frozen=True)
class FileInfo:
    file: str
    rows: int
    row_groups: int
    size_bytes: int
    has_hash_columns: bool
    sorted_by_hash: bool
    prefixed_id: bool
    cloud_optimized: bool


def file_info(path: Path) -> FileInfo:
    parquet_file = ParquetFile(path)
    schema = parquet_file.schema_arrow

    has_hash_columns = all(name in schema.names for name in REQUIRED_HASH_COLUMNS)
    sorted_by_hash = True
    if has_hash_columns:
        hashes = parquet_file.read(columns=["hash:hash"]).column("hash:hash").to_pylist()
        sorted_by_hash = hashes == sorted(hashes)

    prefixed_id = False
    if "id" in schema.names:
        ids = parquet_file.read(columns=["id"]).column("id").to_pylist()
        prefixed_id = bool(ids) and all(
            PREFIXED_ID_PATTERN.match(id_value) for id_value in ids
        )

    return FileInfo(
        file=str(path),
        rows=parquet_file.metadata.num_rows,
        row_groups=parquet_file.metadata.num_row_groups,
        size_bytes=path.stat().st_size,
        has_hash_columns=has_hash_columns,
        sorted_by_hash=sorted_by_hash,
        prefixed_id=prefixed_id,
        cloud_optimized=has_hash_columns and sorted_by_hash,
    )


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def info(
    infiles: Annotated[
        list[Path],
        Argument(
            help="One or more stac-geoparquet files, or directories holding stac-geoparquet files"
        ),
    ],
    as_json: Annotated[
        bool,
        Option("--json", help="Print machine-readable JSON instead of a table"),
    ] = False,
) -> None:
    """Prints info about one or more stac-geoparquet files, including whether each is cloud-optimized."""
    paths = [path for infile in infiles for path in resolve_infiles(infile)]
    results = [file_info(path) for path in paths]

    if as_json:
        print(json.dumps([asdict(result) for result in results], indent=2))
        return

    table = Table(title="stac-geoparquet info")
    table.add_column("file")
    table.add_column("rows", justify="right")
    table.add_column("row groups", justify="right")
    table.add_column("size", justify="right")
    table.add_column("sorted")
    table.add_column("prefixed id")
    table.add_column("cloud-optimized")
    total_rows = 0
    for result in results:
        total_rows += result.rows
        table.add_row(
            Path(result.file).name,
            f"{result.rows:,}",
            str(result.row_groups),
            format_size(result.size_bytes),
            "yes" if result.sorted_by_hash else "no",
            "yes" if result.prefixed_id else "no",
            "yes" if result.cloud_optimized else "no",
        )

    console = Console()
    console.print(table)
    console.print(f"{len(results)} files, {total_rows:,} rows total")
```

- [ ] **Step 2: Register `info` on the root app**

Modify `src/cosgp/cli/__init__.py`:

```python
from __future__ import annotations

from typer import Typer

from .convert import convert
from .info import info

app = Typer()

app.command()(convert)
app.command(name="create")(convert)
app.command()(info)
```

- [ ] **Step 3: Smoke-test against the cloud-optimized output from Task 1**

Run:

```bash
uv run cosgp info /tmp/cosgp-smoke/out
uv run cosgp info /tmp/cosgp-smoke/out --json
```

Expected: the table shows `sorted=yes`, `cloud-optimized=yes` for the converted output (it was produced by `convert`, so it must satisfy its own definition of cloud-optimized); `--json` prints the same fields as a JSON array.

- [ ] **Step 4: Smoke-test against the pre-conversion input (should NOT be cloud-optimized)**

Run: `uv run cosgp info /tmp/cosgp-smoke/in.parquet`
Expected: `sorted=no`, `cloud-optimized=no` (no hash columns at all on the raw input file).

- [ ] **Step 5: Commit**

```bash
git add src/cosgp/cli/info.py src/cosgp/cli/__init__.py
git commit -m "feat: add cosgp info subcommand"
```

---

### Task 3: Port the `benchmark` subcommand from `rework-benchmarking`

**Files:**
- Create: `src/cosgp/cli/benchmark/__init__.py`
- Create: `src/cosgp/cli/benchmark/queries.py`
- Create: `src/cosgp/cli/benchmark/compare.py`
- Create: `src/cosgp/cli/benchmark/runner.py`
- Create: `src/cosgp/cli/benchmark/cli.py`
- Modify: `src/cosgp/cli/__init__.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `cosgp.progress.progress_bar` (existing, unchanged).
- Produces: `cosgp.cli.benchmark.cli.benchmark_app: Typer` with commands `run` and `compare`.

- [ ] **Step 1: Create `src/cosgp/cli/benchmark/__init__.py`** (empty file)

```bash
touch src/cosgp/cli/benchmark/__init__.py
```

- [ ] **Step 2: Create `src/cosgp/cli/benchmark/queries.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_REPEATS = 5


@dataclass(frozen=True)
class Query:
    name: str
    sql: str


QUERIES: list[Query] = [
    Query(
        name="full_dataset_count",
        sql="SELECT count(*) FROM read_parquet({parquet_glob})",
    ),
    Query(
        name="time_range_count",
        sql="SELECT count(*) FROM read_parquet({parquet_glob}) WHERE datetime >= {start_datetime} AND datetime < {end_datetime}",
    ),
    Query(
        name="bbox_count",
        sql="SELECT count(*) FROM read_parquet({parquet_glob}) WHERE bbox.xmax >= {minx} AND bbox.xmin <= {maxx} AND bbox.ymax >= {miny} AND bbox.ymin <= {maxy}",
    ),
    Query(
        name="attribute_filter_count",
        sql='SELECT count(*) FROM read_parquet({parquet_glob}) WHERE "eo:cloud_cover" <= {max_cloud_cover}',
    ),
    Query(
        name="intersects_count",
        sql="SELECT count(*) FROM read_parquet({parquet_glob}) WHERE ST_Intersects(geometry, ST_GeomFromText({aoi_wkt}))",
    ),
    Query(
        name="search_datetime_order",
        sql="SELECT id, collection, datetime FROM read_parquet({parquet_glob}) WHERE datetime >= {start_datetime} AND datetime < {end_datetime} AND bbox.xmax >= {minx} AND bbox.xmin <= {maxx} AND bbox.ymax >= {miny} AND bbox.ymin <= {maxy} ORDER BY datetime, id",
    ),
    Query(
        name="latest_items",
        sql="SELECT id, datetime FROM read_parquet({parquet_glob}) ORDER BY datetime DESC LIMIT 100",
    ),
    Query(
        name="aggregation",
        sql="SELECT date_trunc('month', datetime) AS month, count(*) AS items FROM read_parquet({parquet_glob}) GROUP BY month ORDER BY month",
    ),
    Query(
        name="id",
        sql="SELECT id FROM read_parquet({parquet_glob}) WHERE id = {id}",
    ),
]
```

- [ ] **Step 3: Create `src/cosgp/cli/benchmark/compare.py`**

```python
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass(frozen=True)
class Run:
    dataset_name: str
    dataset_path: str
    results: dict[str, dict]


@dataclass(frozen=True)
class ComparisonRow:
    query: str
    rows_a: int | None
    rows_b: int | None
    median_seconds_a: float
    median_seconds_b: float
    delta_percent: float
    speedup: float
    rows_mismatch: bool


class RunLoadError(Exception):
    pass


def load_run(path: Path) -> Run:
    run_file = path / "run.json" if path.is_dir() else path
    if not run_file.exists():
        raise RunLoadError(f"no run.json found at {run_file}")
    payload = json.loads(run_file.read_text())
    try:
        results = {result["query"]: result for result in payload["results"]}
        return Run(
            dataset_name=payload["dataset_name"],
            dataset_path=payload["dataset_path"],
            results=results,
        )
    except KeyError as e:
        raise RunLoadError(f"{run_file} is not a valid run.json (missing {e})") from e


def compare(run_a: Run, run_b: Run) -> tuple[list[ComparisonRow], list[str]]:
    shared = sorted(set(run_a.results) & set(run_b.results))
    skipped = sorted(set(run_a.results) ^ set(run_b.results))
    rows = []
    for name in shared:
        result_a = run_a.results[name]
        result_b = run_b.results[name]
        median_a = result_a["median_seconds"]
        median_b = result_b["median_seconds"]
        delta_percent = ((median_b - median_a) / median_a) * 100 if median_a else 0.0
        speedup = median_a / median_b if median_b else float("inf")
        rows.append(
            ComparisonRow(
                query=name,
                rows_a=result_a["rows"],
                rows_b=result_b["rows"],
                median_seconds_a=median_a,
                median_seconds_b=median_b,
                delta_percent=delta_percent,
                speedup=speedup,
                rows_mismatch=result_a["rows"] != result_b["rows"],
            )
        )
    return rows, skipped


def render_table(run_a: Run, run_b: Run, rows: list[ComparisonRow]) -> Table:
    table = Table(title=f"{run_a.dataset_name} vs {run_b.dataset_name}")
    table.add_column("query")
    table.add_column(f"{run_a.dataset_name} rows", justify="right")
    table.add_column(f"{run_b.dataset_name} rows", justify="right")
    table.add_column(f"{run_a.dataset_name} median (s)", justify="right")
    table.add_column(f"{run_b.dataset_name} median (s)", justify="right")
    table.add_column("delta median %", justify="right")
    table.add_column("speedup", justify="right")
    for row in rows:
        query_label = f"{row.query} ⚠" if row.rows_mismatch else row.query
        table.add_row(
            query_label,
            str(row.rows_a),
            str(row.rows_b),
            f"{row.median_seconds_a:.4f}",
            f"{row.median_seconds_b:.4f}",
            f"{row.delta_percent:+.1f}%",
            f"{row.speedup:.2f}x",
        )
    return table


def print_comparison(
    run_a: Run, run_b: Run, rows: list[ComparisonRow], skipped: list[str]
) -> None:
    console = Console(width=200)
    console.print(render_table(run_a, run_b, rows))
    if skipped:
        console.print(f"skipped (present in only one run): {', '.join(skipped)}")


def write_markdown(
    run_a: Run, run_b: Run, rows: list[ComparisonRow], outfile: Path
) -> None:
    lines = [
        (
            f"| query | {run_a.dataset_name} rows | {run_b.dataset_name} rows | "
            f"{run_a.dataset_name} median (s) | {run_b.dataset_name} median (s) | "
            f"delta median % | speedup |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        query_label = f"{row.query} ⚠" if row.rows_mismatch else row.query
        lines.append(
            f"| {query_label} | {row.rows_a} | {row.rows_b} | {row.median_seconds_a:.4f} | "
            f"{row.median_seconds_b:.4f} | {row.delta_percent:+.1f}% | {row.speedup:.2f}x |"
        )
    outfile.write_text("\n".join(lines) + "\n")


def write_csv(run_a: Run, run_b: Run, rows: list[ComparisonRow], outfile: Path) -> None:
    with outfile.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "query",
                f"{run_a.dataset_name}_rows",
                f"{run_b.dataset_name}_rows",
                f"{run_a.dataset_name}_median_seconds",
                f"{run_b.dataset_name}_median_seconds",
                "delta_median_percent",
                "speedup",
                "rows_mismatch",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.query,
                    row.rows_a,
                    row.rows_b,
                    row.median_seconds_a,
                    row.median_seconds_b,
                    f"{row.delta_percent:.1f}",
                    f"{row.speedup:.2f}",
                    row.rows_mismatch,
                ]
            )
```

- [ ] **Step 4: Create `src/cosgp/cli/benchmark/runner.py`**

```python
from __future__ import annotations

import datetime
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
from rich.progress import Progress, TaskID

from ...progress import progress_bar
from .queries import DEFAULT_REPEATS, QUERIES, Query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkResult:
    query: str
    rows: int | None
    best_seconds: float
    median_seconds: float
    runs: tuple[float, ...]


PARAMS_SQL = """
SELECT
    quantile_cont(datetime, 0.25) AS start_datetime,
    quantile_cont(datetime, 0.75) AS end_datetime,
    quantile_cont(bbox.xmin, 0.25) AS minx,
    quantile_cont(bbox.xmax, 0.75) AS maxx,
    quantile_cont(bbox.ymin, 0.25) AS miny,
    quantile_cont(bbox.ymax, 0.75) AS maxy,
    quantile_cont("eo:cloud_cover", 0.5) AS max_cloud_cover,
    any_value(id) AS id
FROM read_parquet({parquet_glob})
"""


class BenchmarkRunner:
    def __init__(self, repeats: int = DEFAULT_REPEATS, progress: bool = True) -> None:
        self.repeats = repeats
        self.progress: Progress | None
        if progress:
            self.progress = progress_bar()
        else:
            self.progress = None
        self.connection = duckdb.connect(database=":memory:")
        self.connection.execute("INSTALL spatial")
        self.connection.execute("LOAD spatial")
        self.connection.execute("INSTALL httpfs")
        self.connection.execute("LOAD httpfs")
        self.connection.execute(
            "CREATE OR REPLACE SECRET benchmark_public_s3 ( TYPE s3, PROVIDER config, REGION 'us-west-2', ENDPOINT 's3.us-west-2.amazonaws.com', URL_STYLE 'path', USE_SSL true )"
        )
        self.connection.execute("SET enable_external_file_cache = false")

    def run(self, dataset_name: str, dataset_path: str, out_dir: Path) -> Path:
        if self.progress:
            self.progress.start()
        else:
            logger.info("resolving parameters for %s", dataset_path)
        try:
            params = self.resolve_params(dataset_path)

            task: TaskID | None = None
            if self.progress:
                task = self.progress.add_task(
                    f"benchmarking {len(QUERIES)} queries", total=len(QUERIES)
                )
            else:
                logger.info("benchmarking %d queries", len(QUERIES))
            results = []
            for query in QUERIES:
                results.append(self.run_query(query, dataset_path, params))
                if self.progress and task is not None:
                    self.progress.advance(task)
                else:
                    logger.info("benchmarked %s", query.name)
            if self.progress and task is not None:
                self.progress.remove_task(task)

            return self.write(dataset_name, dataset_path, params, results, out_dir)
        finally:
            if self.progress:
                self.progress.stop()

    def resolve_params(self, dataset_path: str) -> dict[str, object]:
        sql = PARAMS_SQL.format(parquet_glob=sql_literal(dataset_path))
        cursor = self.connection.execute(sql)
        columns = [description[0] for description in cursor.description]
        row = cursor.fetchone()
        assert row is not None
        params = dict(zip(columns, row))
        params["aoi_wkt"] = (
            f"POLYGON(({params['minx']} {params['miny']}, "
            f"{params['maxx']} {params['miny']}, "
            f"{params['maxx']} {params['maxy']}, "
            f"{params['minx']} {params['maxy']}, "
            f"{params['minx']} {params['miny']}))"
        )
        return params

    def run_query(
        self, query: Query, dataset_path: str, params: dict[str, object]
    ) -> BenchmarkResult:
        values = {"parquet_glob": dataset_path, **params}
        sql = query.sql.format(
            **{key: sql_literal(value) for key, value in values.items()}
        )
        rows: int | None = None
        timings: list[float] = []
        repeat_task: TaskID | None = None
        if self.progress:
            repeat_task = self.progress.add_task(
                f"{query.name} ({self.repeats} repeats)", total=self.repeats
            )
        for _ in range(self.repeats):
            started = time.perf_counter()
            result = self.connection.execute(sql).fetchall()
            timings.append(time.perf_counter() - started)
            if (
                len(result) == 1
                and len(result[0]) == 1
                and isinstance(result[0][0], int)
            ):
                rows = result[0][0]
            else:
                rows = len(result)
            if self.progress and repeat_task is not None:
                self.progress.advance(repeat_task)
        if self.progress and repeat_task is not None:
            self.progress.remove_task(repeat_task)
        return BenchmarkResult(
            query=query.name,
            rows=rows,
            best_seconds=min(timings),
            median_seconds=statistics.median(timings),
            runs=tuple(timings),
        )

    def write(
        self,
        dataset_name: str,
        dataset_path: str,
        params: dict[str, object],
        results: list[BenchmarkResult],
        out_dir: Path,
    ) -> Path:
        timestamp = datetime.datetime.now(datetime.UTC)
        run_dir = out_dir / f"{dataset_name}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
        run_dir.mkdir(parents=True)
        payload = {
            "dataset_name": dataset_name,
            "dataset_path": dataset_path,
            "timestamp": timestamp.isoformat(),
            "duckdb_version": duckdb.__version__,
            "repeats": self.repeats,
            "params": params,
            "results": [asdict(result) for result in results],
        }
        run_file = run_dir / "run.json"
        run_file.write_text(json.dumps(payload, indent=2, default=str))
        return run_file


def sql_literal(value: object) -> str:
    if isinstance(value, datetime.datetime):
        return "TIMESTAMPTZ '" + value.isoformat().replace("+00:00", "Z") + "'"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)
```

This is a verbatim port from `rework-benchmarking`'s `src/cosgp/benchmark/runner.py`, with the relative import changed from `from ..progress import progress_bar` to `from ...progress import progress_bar` — `benchmark/` now sits one package level deeper (`cosgp/cli/benchmark/` instead of `cosgp/benchmark/`).

- [ ] **Step 5: Create `src/cosgp/cli/benchmark/cli.py`**

```python
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
```

This is a verbatim port from `rework-benchmarking`'s `src/cosgp/benchmark/cli.py`, with the missing-duckdb error message updated from `` `cosgp-benchmark run` `` to `` `cosgp benchmark run` `` to match the new subcommand path.

- [ ] **Step 6: Wire `benchmark_app` into the root app**

Modify `src/cosgp/cli/__init__.py`:

```python
from __future__ import annotations

from typer import Typer

from .benchmark.cli import benchmark_app
from .convert import convert
from .info import info

app = Typer()

app.command()(convert)
app.command(name="create")(convert)
app.command()(info)
app.add_typer(benchmark_app, name="benchmark")
```

- [ ] **Step 7: Add the `benchmark` optional dependency group to `pyproject.toml`**

Modify `pyproject.toml`, adding (after the `dependencies` array, before `[build-system]`):

```toml
[project.optional-dependencies]
benchmark = ["duckdb>=1.3", "pytz>=2025.2"]
```

- [ ] **Step 8: Verify the app loads without duckdb installed**

Run: `uv run cosgp --help`
Expected: lists `benchmark` alongside `convert`/`create`/`info` — importing `cosgp.cli` must not require `duckdb` (the `import duckdb` in `benchmark/cli.py:run` is inside the function body, deferred).

- [ ] **Step 9: Install the extra and smoke-test `run`/`compare` end-to-end**

```bash
uv sync --extra benchmark
uv run cosgp benchmark run smoke_a "/tmp/cosgp-smoke/out/*.parquet"
uv run cosgp benchmark run smoke_b "/tmp/cosgp-smoke/out2/*.parquet"
uv run cosgp benchmark compare benchmark-results/smoke_a-* benchmark-results/smoke_b-*
```

Expected: two `run.json` files get written under `benchmark-results/`, and `compare` prints a table comparing every query between the two runs with no `rows_mismatch` warnings (both were produced from the same input data).

- [ ] **Step 10: Commit**

```bash
git add src/cosgp/cli/benchmark/ src/cosgp/cli/__init__.py pyproject.toml uv.lock
git commit -m "feat: port benchmark subcommand from rework-benchmarking"
```

---

### Task 4: Update README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the single-command "Usage" section**

Replace the current `## Usage` section (the `uv run cosgp INFILE DATETIME OUTDIR` block and its bullet list) with:

```markdown
## Usage

Install dependencies and run the `cosgp` CLI via [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

`cosgp` has three subcommands: `convert` (aliased `create`), `info`, and `benchmark`.

### `cosgp convert` / `cosgp create`

Re-writes existing stac-geoparquet into cloud-optimized stac-geoparquet:

```sh
uv run cosgp convert INFILE DATETIME OUTDIR
```

- `INFILE`: a stac-geoparquet file, or a directory of `.parquet` files
- `DATETIME`: the datetime range to hash against — a year (`2024`), year-month (`2024-06`), or year-month-day (`2024-06-01`)
- `OUTDIR`: where the cloud-optimized output files are written

For example:

```sh
uv run cosgp convert items.parquet 2024 optimized/
```

Some useful options:

- `--bbox MINX MINY MAXX MAXY`: restrict the hash's spatial extent (defaults to the whole globe)
- `--prefix-id`: prefix each item's `id` with its hash, speeding up single-id lookups
- `--bucket-size BYTES`: target size per output file (default 2 GB uncompressed)
- `--no-progress`: log progress instead of showing a progress bar

Run `uv run cosgp convert --help` for the full list of options. `cosgp create` is an alias for the same command.

### `cosgp info`

Prints info about one or more stac-geoparquet files, including whether each is actually cloud-optimized (has stac-hash columns and is sorted by hash):

```sh
uv run cosgp info optimized/
uv run cosgp info optimized/*.parquet --json
```

### `cosgp benchmark`

Runs a fixed suite of DuckDB queries against one or more stac-geoparquet datasets and compares timings between runs. Requires the `benchmark` extra:

```sh
uv sync --extra benchmark
uv run cosgp benchmark run my-dataset "optimized/*.parquet"
uv run cosgp benchmark compare benchmark-results/run-a-* benchmark-results/run-b-*
```

`path` is passed straight to DuckDB's `read_parquet`, so it can be a local glob or a remote (e.g. `s3://`) URI. See [docs/benchmarks.md](docs/benchmarks.md) for the separate DuckDB notebook used for deeper cross-layout comparisons.
```

- [ ] **Step 2: Review the rendered README**

Run: `cat README.md` and read through it — confirm no leftover references to the old single-command usage remain, and that fenced code blocks are balanced (no stray triple-backticks from the nested example above — write the actual file with single-level fencing, not the doubled fencing used to quote it in this plan step).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document convert/create, info, and benchmark subcommands"
```

---

### Task 5: Full verification pass

**Files:** none (verification only).

- [ ] **Step 1: Lint**

Run: `uv run ruff check .`
Expected: no errors on the new `src/cosgp/cli/` package.

- [ ] **Step 2: Format check**

Run: `uv run ruff format --check .`
Expected: passes; if it reports files needing formatting, run `uv run ruff format .` and review the diff before committing.

- [ ] **Step 3: Type-check**

Run: `uv run basedpyright`
Expected: no errors. Pay particular attention to `src/cosgp/cli/info.py` (dataclass field types) and `src/cosgp/cli/benchmark/runner.py` (the deferred `duckdb` import inside `run()` in `benchmark/cli.py` should not itself cause a type error since it's guarded by `try/except ImportError`).

- [ ] **Step 4: Full test suite**

Run: `uv run pytest`
Expected: PASS (only pre-existing `tests/test_runner.py`; no new tests were added per the global constraint).

- [ ] **Step 5: Clean up smoke-test artifacts**

```bash
rm -rf /tmp/cosgp-smoke benchmark-results
```

(Only remove `benchmark-results/` if it was created fresh by Task 3 Step 9 smoke-testing and doesn't contain prior results you want to keep — check `git status` first, since it's untracked and won't show as a diff either way.)

- [ ] **Step 6: Final commit if anything changed**

If Step 2 or Step 3 produced formatting/type fixes not yet committed:

```bash
git add -u
git commit -m "fix: formatting and type-check fixes"
```
