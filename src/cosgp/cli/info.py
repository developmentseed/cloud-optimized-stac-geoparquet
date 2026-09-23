from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

from pyarrow import Schema
from pyarrow.parquet import ParquetFile
from rich.console import Console
from rich.table import Table
from typer import Argument, Option

from .common import resolve_infiles

REQUIRED_HASH_COLUMNS = ("hash:hash",)
PREFIXED_ID_PATTERN = re.compile(r"^[0-9a-f]{16}-")

MIN_ROW_GROUP_ROWS = 50_000
MAX_ROW_GROUP_ROWS = 150_000
MAX_FILE_SIZE_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class FileInfo:
    file: str
    rows: int
    row_groups: int
    rows_per_row_group: int
    size_bytes: int
    has_hash_columns: bool
    sorted_by_hash: bool
    prefixed_id: bool
    cloud_optimized: bool
    compression: str
    compression_ok: bool
    row_group_size_ok: bool
    file_size_ok: bool
    geoparquet_version: str | None
    has_bbox_covering: bool


def row_group_compression(parquet_file: ParquetFile) -> str:
    codecs = {
        parquet_file.metadata.row_group(i).column(j).compression
        for i in range(parquet_file.metadata.num_row_groups)
        for j in range(parquet_file.metadata.row_group(i).num_columns)
    }
    if len(codecs) == 1:
        return codecs.pop().lower()
    return "mixed"


def geo_metadata(schema: Schema) -> dict[str, Any] | None:
    if schema.metadata is None or b"geo" not in schema.metadata:
        return None
    return json.loads(schema.metadata[b"geo"])


def file_info(path: Path) -> FileInfo:
    parquet_file = ParquetFile(path)
    schema = parquet_file.schema_arrow

    has_hash_columns = all(name in schema.names for name in REQUIRED_HASH_COLUMNS)
    sorted_by_hash = False
    if has_hash_columns:
        hashes = (
            parquet_file.read(columns=["hash:hash"]).column("hash:hash").to_pylist()
        )
        sorted_by_hash = hashes == sorted(hashes)

    prefixed_id = False
    if "id" in schema.names:
        ids = parquet_file.read(columns=["id"]).column("id").to_pylist()
        prefixed_id = bool(ids) and all(
            PREFIXED_ID_PATTERN.match(id_value) for id_value in ids
        )

    rows = parquet_file.metadata.num_rows
    row_groups = parquet_file.metadata.num_row_groups
    size_bytes = path.stat().st_size

    compression = row_group_compression(parquet_file)
    misized_row_groups = sum(
        1
        for i in range(row_groups)
        if not (
            MIN_ROW_GROUP_ROWS
            <= parquet_file.metadata.row_group(i).num_rows
            <= MAX_ROW_GROUP_ROWS
        )
    )
    row_group_size_ok = misized_row_groups <= 1

    geo = geo_metadata(schema)
    geoparquet_version = None
    has_bbox_covering = False
    if geo is not None:
        geoparquet_version = geo.get("version")
        columns = geo.get("columns", {})
        primary_column = columns.get(geo.get("primary_column"), {})
        has_bbox_covering = "covering" in primary_column

    return FileInfo(
        file=str(path),
        rows=rows,
        row_groups=row_groups,
        rows_per_row_group=rows // row_groups if row_groups else 0,
        size_bytes=size_bytes,
        has_hash_columns=has_hash_columns,
        sorted_by_hash=sorted_by_hash,
        prefixed_id=prefixed_id,
        cloud_optimized=has_hash_columns and sorted_by_hash,
        compression=compression,
        compression_ok=compression == "zstd",
        row_group_size_ok=row_group_size_ok,
        file_size_ok=size_bytes < MAX_FILE_SIZE_BYTES,
        geoparquet_version=geoparquet_version,
        has_bbox_covering=has_bbox_covering,
    )


def issues(result: FileInfo) -> str:
    problems = []
    if not result.compression_ok:
        problems.append(f"{result.compression} compression")
    if not result.row_group_size_ok:
        problems.append("row group size")
    if not result.file_size_ok:
        problems.append("file size")
    return ", ".join(problems)


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
    table.add_column("rows/row group", justify="right")
    table.add_column("size", justify="right")
    table.add_column("sorted")
    table.add_column("prefixed id")
    table.add_column("cloud-optimized")
    table.add_column("geoparquet version")
    table.add_column("bbox covering")
    table.add_column("issues")
    total_rows = 0
    for result in results:
        total_rows += result.rows
        table.add_row(
            Path(result.file).name,
            f"{result.rows:,}",
            str(result.row_groups),
            f"{result.rows_per_row_group:,}",
            format_size(result.size_bytes),
            "yes" if result.sorted_by_hash else "no",
            "yes" if result.prefixed_id else "no",
            "yes" if result.cloud_optimized else "no",
            result.geoparquet_version or "-",
            "yes" if result.has_bbox_covering else "no",
            issues(result) or "-",
        )

    console = Console()
    console.print(table)
    console.print(f"{len(results)} files, {total_rows:,} rows total")
