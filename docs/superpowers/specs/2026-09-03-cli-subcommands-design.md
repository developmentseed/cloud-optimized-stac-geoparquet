# CLI subcommand rewrite

## Goal

Restructure `cosgp` from a single-command CLI into a multi-subcommand CLI:

- `cosgp convert` — convert existing STAC items into cloud-optimized
  stac-geoparquet. Aliased as `cosgp create` (current behavior, current name).
- `cosgp info` — print info about one or more stac-geoparquet files,
  including whether each is actually cloud-optimized.
- `cosgp benchmark` — run a benchmark suite against one or more
  stac-geoparquet files, and compare prior runs.

Subcommands share common setup/config logic (glob resolution, logging setup)
rather than duplicating it.

## Non-goals

- No test coverage is being added or ported as part of this work.
- No changes to the conversion algorithm itself (`Runner` in
  `src/cosgp/runner.py` is unchanged).
- No new benchmark queries or comparison formats beyond what already exists
  on the `rework-benchmarking` branch.

## Background

`rework-benchmarking` is a branch that forked off `90896d4` (before the
`mixed schemas` / rename / `match-file-count` fixes landed on
`vibe-rewrite`) and built a working DuckDB-based benchmark tool, shipped as a
**separate** script (`cosgp-benchmark`, from `cosgp.benchmark.cli:benchmark_app`)
with `duckdb`/`pytz` as an optional `benchmark` extra. That implementation
(`src/cosgp/benchmark/{cli,runner,compare,queries}.py`) is being ported
forward and rewired as a subcommand of the main `cosgp` app.

## Package layout

`src/cosgp/cli.py` (single file) becomes a package:

```
src/cosgp/cli/
├── __init__.py      # root Typer `app`; registers convert/create/info/benchmark
├── common.py        # shared Datetime parser, resolve_infiles(), configure_logging()
├── convert.py        # convert/create command (moved from current cli.py)
├── info.py           # new info command
└── benchmark/
    ├── __init__.py
    ├── cli.py         # benchmark_app: run, compare (ported from rework-benchmarking)
    ├── runner.py       # duckdb BenchmarkRunner (ported)
    ├── compare.py      # Run loading/comparison/rendering (ported)
    └── queries.py      # fixed query suite (ported)
```

`runner.py` (the conversion `Runner`) and `progress.py` stay at the top level
of `src/cosgp/` — they are not CLI concerns.

## Shared config / glob logic (`cli/common.py`)

- `resolve_infiles(infile: Path, pattern: str = "*.parquet") -> list[Path]`
  — the file-or-directory glob logic currently inlined in `create()` in
  `cli.py`, extracted so `convert` and `info` both use it. Raises
  `ValueError` if no matching files are found, same as current behavior.
- `configure_logging(progress: bool) -> None` — the
  `if not progress: logging.basicConfig(...)` idiom, shared by `convert` and
  `benchmark run`.
- `Datetime` — moves here unchanged from the current `cli.py`.

No shared options dataclass or Typer callback: `convert`, `info`, and
`benchmark run` take different enough parameter shapes (single
infile+datetime+outdir vs. variadic file list vs. name+duckdb-glob-string)
that a shared callback would force awkward common flags across commands that
don't all need them. Plain shared functions are sufficient.

## `convert` / `create`

Moves into `cli/convert.py` essentially unchanged from the current `create()`
in `cli.py`, using `resolve_infiles`/`configure_logging` from `common.py`.
Registered under both names by wrapping a single implementation function with
two `@app.command()` registrations (`convert`, `create`) so both invoke
identical behavior. The full docstring/help lives on `convert`; `create` is a
thin alias without a duplicated docstring.

## `info` (new)

```
cosgp info INFILES...  [--json]
```

- `infiles: list[Path]` — one or more files or directories; each resolved via
  `resolve_infiles` and flattened into one list of parquet files.
- For each file, inspect via `pyarrow.parquet.ParquetFile` metadata plus a
  single-column read of `hash:hash`:
  - row count
  - row group count
  - file size (bytes)
  - whether hash columns (`hash:hash`, `hash:start_datetime`,
    `hash:end_datetime`, optionally `hash:bbox`) are present
  - whether `hash:hash` values are monotonically non-decreasing (sorted)
  - whether `id` values look hash-prefixed (regex `^[0-9a-f]{16}-`)
  - `cloud-optimized` verdict: `True` iff hash columns are present **and**
    the file is sorted by hash.
- Default output: a `rich.Table` (styled like the existing table rendering
  in `benchmark/compare.py`) plus a totals summary line (file count, total
  rows).
- `--json`: emit the same per-file fields as JSON instead of the table, for
  scripting.

## `benchmark` (ported from `rework-benchmarking`)

- `runner.py`, `compare.py`, `queries.py` port over essentially unchanged:
  the fixed DuckDB query suite, timing/repeats, `run.json` output format, and
  the comparison table/markdown/CSV writers.
- `cli.py`'s `benchmark_app` is nested into the root app via
  `app.add_typer(benchmark_app, name="benchmark")` instead of being shipped
  as the separate `cosgp-benchmark` script.
- `duckdb`/`pytz` stay in an optional `benchmark` extra
  (`pip install cosgp[benchmark]` / `uv sync --extra benchmark`);
  `cosgp benchmark run`'s lazy `import duckdb` keeps its existing friendly
  error (with install instructions) if the extra isn't installed.
- `pyproject.toml` drops the `cosgp-benchmark` script entry — `cosgp` is now
  the only entry point.
- Result: `cosgp benchmark run NAME PATH` and
  `cosgp benchmark compare RUN_A RUN_B` behave as they did on
  `rework-benchmarking`, just reached via the main `cosgp` app.

## Testing

None added or ported as part of this work, per explicit instruction.
`tests/test_runner.py` is left untouched since the conversion `Runner` isn't
changing.

## Documentation

`README.md` gets updated to document the three subcommands
(`convert`/`create`, `info`, `benchmark`) in place of the current
single-command usage section, folding in the benchmark usage notes
currently split across `README.md` and `docs/benchmarks.md`.
