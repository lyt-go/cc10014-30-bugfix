"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import raw_ingest as router_raw_ingest
from app.routers import column_mapping as router_column_mapping
from app.routers import cleanse_rule as router_cleanse_rule
from app.routers import dedup_config as router_dedup_config
from app.routers import ods_layer as router_ods_layer
from app.routers import dwd_layer as router_dwd_layer
from app.routers import dws_layer as router_dws_layer
from app.routers import dim_model as router_dim_model
from app.routers import snapshot_mgr as router_snapshot_mgr
from app.routers import partition_mgr as router_partition_mgr
from app.routers import quality_check as router_quality_check
from app.routers import lineage_track as router_lineage_track
from app.routers import backfill_job as router_backfill_job
from app.routers import table_compare as router_table_compare
from app.routers import schema_registry as router_schema_registry
from app.routers import schema_version_view as router_schema_version_view
from app.routers import data_publish as router_data_publish
from app.routers import transform_dag as router_transform_dag
from app.routers import cold_archive as router_cold_archive

ROUTERS = [router_raw_ingest, router_column_mapping, router_cleanse_rule, router_dedup_config, router_ods_layer, router_dwd_layer, router_dws_layer, router_dim_model, router_snapshot_mgr, router_partition_mgr, router_quality_check, router_lineage_track, router_backfill_job, router_table_compare, router_schema_registry, router_schema_version_view, router_data_publish, router_transform_dag, router_cold_archive]
