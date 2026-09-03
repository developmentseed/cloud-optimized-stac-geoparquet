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
