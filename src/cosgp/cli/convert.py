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
