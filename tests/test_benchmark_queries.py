from cosgp.cli.benchmark.queries import Query
from cosgp.cli.benchmark.runner import runnable_queries


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
