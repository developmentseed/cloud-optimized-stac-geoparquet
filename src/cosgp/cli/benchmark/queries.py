from __future__ import annotations

from dataclasses import dataclass

DEFAULT_REPEATS = 5


@dataclass(frozen=True)
class Query:
    name: str
    sql: str
    required_columns: tuple[str, ...] = ()
    required_params: tuple[str, ...] = ()


QUERIES: list[Query] = [
    Query(
        name="q01_full_dataset_count",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
""",
    ),
    Query(
        name="q02_time_range_count",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE datetime >= {start_datetime}
  AND datetime < {end_datetime}
""",
    ),
    Query(
        name="q03_bbox_count",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
    ),
    Query(
        name="q04_stac_search_count",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
    Query(
        name="q05_hash_range_search",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE "hash:hash" BETWEEN {min_hash} AND {max_hash}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
        required_columns=("hash:hash",),
        required_params=("min_hash", "max_hash"),
    ),
    Query(
        name="q06_search_page_datetime_order",
        sql="""
SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
ORDER BY datetime, id
LIMIT 100
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
    Query(
        name="q06_search_page_hash_order",
        sql="""
SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
ORDER BY "hash:hash", id
LIMIT 100
""",
        required_columns=("collection", "hash:hash"),
        required_params=("collection",),
    ),
    Query(
        name="q07_attribute_filter",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
  AND "eo:cloud_cover" <= {max_cloud_cover}
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
    Query(
        name="q08_exact_geometry_intersects",
        sql="""
SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
  AND ST_Intersects(geometry, ST_GeomFromText({aoi_wkt}))
""",
    ),
    Query(
        name="q09_grouped_aggregation",
        sql="""
SELECT
    collection,
    date_trunc('month', datetime) AS month,
    count(*) AS items
FROM read_parquet({parquet_glob}, hive_partitioning = false)
GROUP BY collection, month
ORDER BY collection, month
""",
        required_columns=("collection",),
    ),
    Query(
        name="q10_collection_latest_items",
        sql="""
SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
ORDER BY datetime DESC
LIMIT 100
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
    Query(
        name="q11_specific_id_lookup",
        sql="""
SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE id = {id}
""",
        required_columns=("collection",),
    ),
    Query(
        name="q11_scoped_id_lookup",
        sql="""
SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND id = {id}
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
]
