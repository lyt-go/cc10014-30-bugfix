"""结构版本诊断视图：语义版本选择、冲突边界、增量续写与历史回查。

验证：
- 同名表结构版本按语义版本（自然顺序）选择，v10 不再排在 v9 之前
- 诊断视图落库的自然顺序、当前版本与当前来源和结构注册解析结果一致
- 手工 v10 与血缘推导 v10 冲突时按业务日期区分较窄/较宽边界
- 定义版本中断后只续写未完成部分，旧诊断记录可回查
"""
from __future__ import annotations

from app.store import store
from app.services.schema_registry import (
    SchemaRegistryService,
    next_version,
    version_sort_key,
)
from app.services.schema_version_view import SchemaVersionViewService


def reset_store():
    from app.seed import SEED_ROWS
    store._tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
    store._table_data.clear()
    store._versions.clear()
    store._lineage_edges.clear()
    store._quality_results.clear()
    store._snapshot_data.clear()
    store._archive_records.clear()
    store._backfill_partitions.clear()


def make_schema(svc, table, version, code, source="手工", biz="2026-11-05"):
    entry, missing = svc.create_entry({
        "定义编号": code,
        "表名称": table,
        "字段名称": "a,b",
        "字段类型": "STRING,STRING",
        "可空标识": "N,N",
        "默认值": ",",
        "定义版本": version,
        "生效批次": "",
        "版本来源": source,
        "业务日期": biz,
    })
    assert not missing
    return entry


class TestSemanticVersionSelection:
    def setup_method(self):
        reset_store()

    def test_version_sort_key_semantic(self):
        """语义版本键：v9 < v10，且支持多级版本号。"""
        assert version_sort_key("v9") < version_sort_key("v10")
        assert version_sort_key("v1") < version_sort_key("v1.1")
        assert next_version("v9") == "v10"
        assert next_version("v10") == "v11"

    def test_current_version_not_string_sorted(self):
        """当前结构按语义版本选择：v10 是当前版本而不是 v9。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_sem", "v9", "SCH-SEM-9")
        make_schema(svc, "dw_sem", "v10", "SCH-SEM-10")
        resolution = svc.resolve_current_entry("dw_sem")
        assert resolution is not None
        assert resolution["当前版本"] == "v10"
        assert resolution["当前来源"] == "手工"
        latest = svc.get_latest_schema("dw_sem")
        assert latest is not None
        assert latest["定义版本"] == "v10"

    def test_view_natural_order_and_current(self):
        """诊断视图按自然版本顺序落库，当前版本与来源标注正确。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_view", "v1", "SCH-VIEW-1")
        make_schema(svc, "dw_view", "v9", "SCH-VIEW-9")
        make_schema(svc, "dw_view", "v10", "SCH-VIEW-10")
        view = SchemaVersionViewService()
        view.refresh()
        rows = view.list_for_table("dw_view")
        assert [row["定义版本"] for row in rows] == ["v1", "v9", "v10"]
        assert [row["自然顺序"] for row in rows] == [1, 2, 3]
        current = [row for row in rows if row["是否当前"] == "是"]
        assert len(current) == 1
        assert current[0]["定义版本"] == "v10"
        assert current[0]["当前来源"] == "手工"
        assert all(row["记录状态"] == "已完成" for row in rows)

    def test_derive_uses_semantic_latest(self):
        """血缘推导基于语义版本递增：已有 v10 时推导 v11，不再撞 v10。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_derive", "v9", "SCH-DERV-9")
        make_schema(svc, "dw_derive", "v10", "SCH-DERV-10")
        store.add_lineage("ods_orders", "dw_derive", "order_id",
                          transform_logic="字段透传", batch_id="RAW-20261101")
        derived = svc.derive_schema_from_lineage("dw_derive", business_date="2026-11-18")
        assert derived is not None
        assert derived["定义版本"] == "v11"
        assert derived["版本来源"] == "血缘推导"

    def test_view_current_consistent_with_registry(self):
        """视图当前引用与结构注册解析、血缘推导基数三者一致。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_consist", "v9", "SCH-CONS-9")
        make_schema(svc, "dw_consist", "v10", "SCH-CONS-10")
        view = SchemaVersionViewService()
        view.refresh()
        rows = view.list_for_table("dw_consist")
        view_current = next(row for row in rows if row["是否当前"] == "是")
        resolution = svc.resolve_current_entry("dw_consist")
        assert view_current["定义版本"] == resolution["当前版本"]
        assert view_current["当前来源"] == resolution["当前来源"]
        store.add_lineage("ods_orders", "dw_consist", "order_id",
                          transform_logic="字段透传", batch_id="RAW-20261101")
        derived = svc.derive_schema_from_lineage("dw_consist", business_date="2026-11-18")
        assert derived is not None
        assert derived["定义版本"] == next_version(view_current["定义版本"])


class TestConflictBoundary:
    def setup_method(self):
        reset_store()

    def test_narrow_boundary_manual_current(self):
        """较窄边界（同一业务月份）：手工当前版本 + 推导候选。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_narrow", "v10", "SCH-NAR-10", source="手工", biz="2026-11-05")
        make_schema(svc, "dw_narrow", "v10", "SCH-DERIVED-dw_narrow-v10",
                    source="血缘推导", biz="2026-11-20")
        view = SchemaVersionViewService()
        view.refresh()
        rows = {row["版本来源"]: row for row in view.list_for_table("dw_narrow")}
        manual, derived = rows["手工"], rows["血缘推导"]
        assert manual["是否当前"] == "是"
        assert manual["当前来源"] == "手工"
        assert derived["是否当前"] == "否"
        assert derived["冲突标记"] == "版本冲突"
        assert derived["冲突处理"] == "推导候选"
        assert derived["跨月标记"] == "否"
        assert manual["冲突标记"] == "版本冲突"

    def test_wide_boundary_derived_current(self):
        """较宽边界（跨业务月份）：推导当前版本 + 手工审核差异。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_wide", "v10", "SCH-WIDE-10", source="手工", biz="2026-10-28")
        make_schema(svc, "dw_wide", "v10", "SCH-DERIVED-dw_wide-v10",
                    source="血缘推导", biz="2026-11-03")
        view = SchemaVersionViewService()
        view.refresh()
        rows = {row["版本来源"]: row for row in view.list_for_table("dw_wide")}
        manual, derived = rows["手工"], rows["血缘推导"]
        assert derived["是否当前"] == "是"
        assert derived["当前来源"] == "血缘推导"
        assert manual["是否当前"] == "否"
        assert manual["冲突标记"] == "版本冲突"
        assert manual["冲突处理"] == "手工审核差异"
        assert manual["跨月标记"] == "是"

    def test_conflict_resolution_matches_registry(self):
        """两种冲突结果下，视图当前引用与结构注册解析保持一致。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_cm", "v10", "SCH-CM-10", source="手工", biz="2026-10-28")
        make_schema(svc, "dw_cm", "v10", "SCH-DERIVED-dw_cm-v10",
                    source="血缘推导", biz="2026-11-03")
        view = SchemaVersionViewService()
        view.refresh()
        resolution = svc.resolve_current_entry("dw_cm")
        assert resolution["冲突"] is not None
        assert resolution["冲突"]["边界"] == "较宽边界"
        assert resolution["当前来源"] == "血缘推导"
        rows = view.list_for_table("dw_cm")
        current = next(row for row in rows if row["是否当前"] == "是")
        assert current["版本来源"] == "血缘推导"


class TestIncrementalRefresh:
    def setup_method(self):
        reset_store()

    def test_create_writes_unfinished_placeholder(self):
        """结构注册入口提交后，诊断视图出现未完成占位记录。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_ph", "v1", "SCH-PH-1")
        view = SchemaVersionViewService()
        rows = view.list_for_table("dw_ph")
        assert len(rows) == 1
        assert rows[0]["记录状态"] == "未完成"
        assert rows[0]["版本来源"] == "手工"

    def test_refresh_only_completes_unfinished(self):
        """中断后续写：只补全未完成部分，已完成记录不被重写。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_inc", "v1", "SCH-INC-1")
        view = SchemaVersionViewService()
        stats1 = view.refresh()
        assert stats1["续写完成"] == 1
        row_v1 = view.list_for_table("dw_inc")[0]
        assert row_v1["记录状态"] == "已完成"
        generated_at = row_v1["生成时间"]
        history_len = len(view.get_history(row_v1["id"]))
        # 新增 v2 后再次刷新：只续写 v2，v1 的诊断内容不重写
        make_schema(svc, "dw_inc", "v2", "SCH-INC-2")
        stats2 = view.refresh()
        assert stats2["续写完成"] == 1
        assert stats2["新建记录"] == 0
        row_v1_after = next(row for row in view.list_for_table("dw_inc") if row["定义版本"] == "v1")
        assert row_v1_after["生成时间"] == generated_at
        assert row_v1_after["记录状态"] == "已完成"
        # v1 的当前标记被一致性核对翻转为否，历史快照留痕可回查
        assert row_v1_after["是否当前"] == "否"
        assert len(view.get_history(row_v1["id"])) > history_len

    def test_refresh_idempotent(self):
        """无变更时重复刷新不产生新记录，也不重复修正。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_idem", "v1", "SCH-IDEM-1")
        view = SchemaVersionViewService()
        view.refresh()
        stats = view.refresh()
        assert stats["新建记录"] == 0
        assert stats["续写完成"] == 0
        assert stats["一致性修正"] == 0

    def test_history_queryable(self):
        """旧诊断记录可回查：历史快照保留，旧版本记录仍在视图中。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_hist", "v1", "SCH-HIST-1")
        view = SchemaVersionViewService()
        view.refresh()
        make_schema(svc, "dw_hist", "v2", "SCH-HIST-2")
        view.refresh()
        rows = view.list_for_table("dw_hist")
        assert [row["定义版本"] for row in rows] == ["v1", "v2"]
        row_v1 = rows[0]
        history = view.get_history(row_v1["id"])
        assert len(history) >= 1
        # 历史快照中能看到 v1 曾经是当前版本
        assert any(item["data"].get("是否当前") == "是" for item in history)


class TestViewSummary:
    def setup_method(self):
        reset_store()

    def test_summary_counts(self):
        """汇总统计：覆盖表数、当前来源分布、冲突与未完成量。"""
        svc = SchemaRegistryService()
        make_schema(svc, "dw_sum_a", "v1", "SCH-SUM-A1")
        make_schema(svc, "dw_sum_a", "v2", "SCH-SUM-A2")
        make_schema(svc, "dw_sum_b", "v10", "SCH-SUM-B10", source="手工", biz="2026-10-28")
        make_schema(svc, "dw_sum_b", "v10", "SCH-DERIVED-dw_sum_b-v10",
                    source="血缘推导", biz="2026-11-03")
        view = SchemaVersionViewService()
        view.refresh()
        summary = view.summary()
        # 种子数据另有 ods_orders/ods_payments/ods_users 三张手工当前表
        assert summary["覆盖表数"] == 2 + 3
        assert summary["手工当前数"] == 1 + 3
        assert summary["血缘当前数"] == 1
        assert summary["版本冲突数"] == 1
        assert summary["未完成数"] == 0

    def test_derive_chain_writes_placeholder(self):
        """血缘推导链路同样写入诊断视图占位，来源模块为血缘追踪。"""
        svc = SchemaRegistryService()
        store.add_lineage("ods_orders", "dw_chain", "order_id",
                          transform_logic="字段透传", batch_id="RAW-20261101")
        derived = svc.derive_schema_from_lineage("dw_chain", business_date="2026-11-18")
        assert derived is not None
        view = SchemaVersionViewService()
        rows = view.list_for_table("dw_chain")
        assert len(rows) == 1
        assert rows[0]["版本来源"] == "血缘推导"
        assert rows[0]["来源模块"] == "lineage_track"
        assert rows[0]["记录状态"] == "未完成"
        view.refresh()
        row = view.list_for_table("dw_chain")[0]
        assert row["记录状态"] == "已完成"
        assert row["是否当前"] == "是"
        assert row["当前来源"] == "血缘推导"
        assert row["调用链"].startswith("血缘推导")
