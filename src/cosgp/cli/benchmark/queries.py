from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DEFAULT_REPEATS = 5


class BenchmarkSuite(str, Enum):
    core = "core"
    composite = "composite"
    all = "all"


@dataclass(frozen=True)
class Query:
    name: str
    sql: str
    required_columns: tuple[str, ...] = ()
    required_params: tuple[str, ...] = ()
    suite: BenchmarkSuite = BenchmarkSuite.core


QUERIES: list[Query] = [
    Query(
        name="full_dataset_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
""",
    ),
    Query(
        name="datetime_range_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE datetime >= {start_datetime}
  AND datetime < {end_datetime}
""",
        required_columns=("datetime",),
        required_params=("start_datetime", "end_datetime"),
    ),
    Query(
        name="bbox_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
        required_columns=("bbox",),
        required_params=("minx", "maxx", "miny", "maxy"),
    ),
    Query(
        name="collection_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
""",
        required_columns=("collection",),
        required_params=("collection",),
    ),
    Query(
        name="hash_range_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE "hash:hash" BETWEEN {min_hash} AND {max_hash}
""",
        required_columns=("hash:hash",),
        required_params=("min_hash", "max_hash"),
    ),
    Query(
        name="datetime_order_page",
        sql="""SELECT datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
ORDER BY datetime
LIMIT 100
""",
        required_columns=("datetime",),
    ),
    Query(
        name="hash_order_page",
        sql="""SELECT "hash:hash"
FROM read_parquet({parquet_glob}, hive_partitioning = false)
ORDER BY "hash:hash"
LIMIT 100
""",
        required_columns=("hash:hash",),
    ),
    Query(
        name="cloud_cover_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE "eo:cloud_cover" <= {max_cloud_cover}
""",
        required_columns=("eo:cloud_cover",),
        required_params=("max_cloud_cover",),
    ),
    Query(
        name="geometry_intersects_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE ST_Intersects(geometry, ST_GeomFromText({aoi_wkt}))
""",
        required_columns=("geometry", "bbox"),
        required_params=("aoi_wkt",),
    ),
    Query(
        name="id_lookup",
        sql="""SELECT id
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE id = {id}
""",
        required_columns=("id",),
        required_params=("id",),
    ),
    Query(
        name="composite_stac_search_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
        required_columns=("collection", "datetime", "bbox"),
        required_params=(
            "collection",
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_hash_stac_search_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE "hash:hash" BETWEEN {min_hash} AND {max_hash}
  AND datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
""",
        required_columns=("hash:hash", "datetime", "bbox"),
        required_params=(
            "min_hash",
            "max_hash",
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_cloud_stac_search_count",
        sql="""SELECT count(*)
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
        required_columns=("collection", "datetime", "bbox", "eo:cloud_cover"),
        required_params=(
            "collection",
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
            "max_cloud_cover",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_geometry_stac_search_count",
        sql="""SELECT count(*)
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE datetime >= {start_datetime}
  AND datetime < {end_datetime}
  AND bbox.xmax >= {minx}
  AND bbox.xmin <= {maxx}
  AND bbox.ymax >= {miny}
  AND bbox.ymin <= {maxy}
  AND ST_Intersects(geometry, ST_GeomFromText({aoi_wkt}))
""",
        required_columns=("datetime", "bbox", "geometry"),
        required_params=(
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
            "aoi_wkt",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_stac_datetime_order_page",
        sql="""SELECT id, collection, datetime
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
        required_columns=("id", "collection", "datetime", "bbox"),
        required_params=(
            "collection",
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_stac_hash_order_page",
        sql="""SELECT id, collection, datetime
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
        required_columns=("id", "collection", "datetime", "bbox", "hash:hash"),
        required_params=(
            "collection",
            "start_datetime",
            "end_datetime",
            "minx",
            "maxx",
            "miny",
            "maxy",
        ),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_collection_month_count",
        sql="""SELECT
    collection,
    date_trunc('month', datetime) AS month,
    count(*) AS items
FROM read_parquet({parquet_glob}, hive_partitioning = false)
GROUP BY collection, month
ORDER BY collection, month
""",
        required_columns=("collection", "datetime"),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_collection_latest_items",
        sql="""SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
ORDER BY datetime DESC
LIMIT 100
""",
        required_columns=("id", "collection", "datetime"),
        required_params=("collection",),
        suite=BenchmarkSuite.composite,
    ),
    Query(
        name="composite_scoped_id_lookup",
        sql="""SELECT id, collection, datetime
FROM read_parquet({parquet_glob}, hive_partitioning = false)
WHERE collection = {collection}
  AND id = {id}
""",
        required_columns=("id", "collection", "datetime"),
        required_params=("collection", "id"),
        suite=BenchmarkSuite.composite,
    ),
]
