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
    any_value(collection) AS collection,
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
            columns = self.dataset_columns(dataset_path)
            params = self.resolve_params(dataset_path)
            queries = runnable_queries(QUERIES, columns, params)

            task: TaskID | None = None
            if self.progress:
                task = self.progress.add_task(
                    f"benchmarking {len(queries)} queries", total=len(queries)
                )
            else:
                logger.info("benchmarking %d queries", len(queries))
            results = []
            for query in queries:
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

    def dataset_columns(self, dataset_path: str) -> set[str]:
        cursor = self.connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({sql_literal(dataset_path)}) LIMIT 0"
        )
        return {row[0] for row in cursor.fetchall()}

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


def runnable_queries(
    queries: list[Query], columns: set[str], params: dict[str, object]
) -> list[Query]:
    return [
        query
        for query in queries
        if all(column in columns for column in query.required_columns)
        and all(param in params for param in query.required_params)
    ]
