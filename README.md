# cloud-optimized-stac-geoparquet

Given one or more **stac-geoparquet** files, re-write them into spatio-temporal-optimized **stac-geoparquet** by sorting them by their [**stac-hash**](https://www.gadom.ski/stac-hash/).
Optionally, prefix item ids by their hash value, drastically improving the performance of single-id searches against the **stac-geoparquet**.

This tool formats **stac-geoparquet** files per the [best practices](https://github.com/radiantearth/stac-geoparquet-spec/blob/main/docs/best-practices.md).

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
uv run cosgp benchmark run my-dataset "optimized/*.parquet" --suite all
uv run cosgp benchmark compare benchmark-results/run-a-* benchmark-results/run-b-*
```

`path` is passed straight to DuckDB's `read_parquet`, so it can be a local glob or a remote (e.g. `s3://`) URI. See [notebooks/duckdb-geoparquet-benchmarks.ipynb](notebooks/duckdb-geoparquet-benchmarks.ipynb) for a deeper cross-layout comparison against files retrieved from the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/).

The default `core` suite isolates one filter or ordering dimension per query. Use
`--suite composite` for realistic searches that combine multiple predicates, or
`--suite all` to run both. Query parameters are derived from each dataset, and
queries whose columns are unavailable are recorded as skipped in `run.json`.

## Benchmarks

The notebook syncs its own sample data and generates hash-sorted variants with `cosgp convert`, so it takes a while to run the first time:

```sh
uv sync --extra benchmark --group notebooks
uv run --group notebooks jupyter lab notebooks/duckdb-geoparquet-benchmarks.ipynb
```

## License

[MIT](LICENSE)
