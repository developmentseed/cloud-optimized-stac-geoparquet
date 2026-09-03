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
    sorted_by_hash = False
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
