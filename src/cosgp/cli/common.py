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
