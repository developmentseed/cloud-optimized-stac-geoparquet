import datetime as dt
from pathlib import Path
from string import Formatter

import duckdb
import pyarrow
import pyarrow.parquet

from cosgp.cli.benchmark.queries import QUERIES, BenchmarkSuite, Query
from cosgp.cli.benchmark.runner import (
    BenchmarkRunner,
    queries_for_suite,
    runnable_queries,
    skipped_queries,
)


def test_runnable_queries_filters_missing_columns_and_params() -> None:
    queries = [
        Query(name="base", sql="SELECT 1"),
        Query(name="needs_column", sql="SELECT 1", required_columns=("hash:hash",)),
        Query(name="needs_param", sql="SELECT 1", required_params=("min_hash",)),
        Query(
            name="needs_both",
            sql="SELECT 1",
            required_columns=("hash:hash",),
            required_params=("min_hash",),
        ),
    ]

    runnable = runnable_queries(queries, columns={"hash:hash"}, params={})

    assert [query.name for query in runnable] == ["base", "needs_column"]


def test_query_suites_keep_composite_filters_out_of_core() -> None:
    core = queries_for_suite(QUERIES, BenchmarkSuite.core)
    composite = queries_for_suite(QUERIES, BenchmarkSuite.composite)

    assert core
    assert composite
    assert all(query.suite is BenchmarkSuite.core for query in core)
    assert all(query.suite is BenchmarkSuite.composite for query in composite)
    assert queries_for_suite(QUERIES, BenchmarkSuite.all) == QUERIES


def test_queries_declare_every_template_parameter() -> None:
    for query in QUERIES:
        placeholders = {
            field_name
            for _, field_name, _, _ in Formatter().parse(query.sql)
            if field_name is not None and field_name != "parquet_glob"
        }
        assert placeholders == set(query.required_params), query.name


def test_skipped_queries_explain_missing_requirements() -> None:
    queries = [
        Query(
            name="optional",
            sql="SELECT 1",
            required_columns=("collection",),
            required_params=("collection",),
        )
    ]

    assert skipped_queries(queries, {"id"}, {}) == {
        "optional": "missing columns: collection; missing parameters: collection"
    }


def test_resolve_params_only_uses_available_columns(tmp_path: Path) -> None:
    path = tmp_path / "minimal.parquet"
    table = pyarrow.table(
        {
            "id": ["landsat-item-a", "landsat-item-b"],
            "datetime": pyarrow.array(
                [
                    dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
                    dt.datetime(2024, 2, 1, tzinfo=dt.UTC),
                ],
                type=pyarrow.timestamp("us", tz="UTC"),
            ),
        }
    )
    pyarrow.parquet.write_table(table, path)
    runner = object.__new__(BenchmarkRunner)
    runner.connection = duckdb.connect(database=":memory:")

    params = runner.resolve_params(str(path), {"id", "datetime"})

    assert params["id"] in {"landsat-item-a", "landsat-item-b"}
    assert "start_datetime" in params
    assert "end_datetime" in params
    assert "collection" not in params
    assert "max_cloud_cover" not in params
