"""结构版本诊断视图：按语义版本自然顺序落库同名表的结构版本诊断结果。

视图职责：
- 以自然版本顺序展示同名表的全部结构版本，标注当前版本与当前来源（手工/血缘推导）；
- 手工与血缘推导同版本冲突时，按业务日期判定较窄/较宽边界并分别记录处理结果；
- 定义版本中断后只续写未完成部分，已完成记录不被重写；
- 每次刷新对全表做版本排序与当前结构引用的一致性核对，保证落库一致；
- 历史记录通过版本快照保留，支持回查。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.schema_registry import (
    SOURCE_DERIVED,
    SOURCE_MANUAL,
    SchemaRegistryService,
    entry_business_date,
    entry_source,
    version_sort_key,
)
from app.store import store

MODULE = "schema_version_view"
LIST_FIELDS = [
    "视图编号", "表名称", "定义版本", "自然顺序", "是否当前", "版本来源",
    "当前来源", "冲突标记", "冲突处理", "业务日期", "跨月标记", "记录状态",
]
STATUS_ORDER = ["待确认", "已复核"]
ACTION_RULES = {"标记复核": "已复核"}
NEGATIVE_ACTIONS = []

SOURCE_CODE = {SOURCE_MANUAL: "M", SOURCE_DERIVED: "L"}
SOURCE_MODULE = {SOURCE_MANUAL: "schema_registry", SOURCE_DERIVED: "lineage_track"}


def view_code(table_name: str, version: str, source: str) -> str:
    return f"SVW-{table_name}-{version}-{SOURCE_CODE.get(source, 'X')}"


def _version_number(version: object) -> int:
    key = version_sort_key(version)[0]
    return key[0] if key else 0


class SchemaVersionViewService:
    # ---- 查询 ----

    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for field, expected in (filters or {}).items():
            rows = [row for row in rows if expected.casefold() in str(row.get(field, "")).casefold()]
        if keyword:
            rows = [row for row in rows if keyword.casefold() in str(row.get("视图编号", "")).casefold()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        # 视图按自然版本顺序展示：表名称 + 语义版本键 + 来源
        rows = sorted(rows, key=self._row_sort_key)
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def list_for_table(self, table_name: str) -> list[dict[str, Any]]:
        rows = [row for row in store.rows(MODULE) if row.get("表名称") == table_name]
        return sorted(rows, key=self._row_sort_key)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def get_history(self, entry_id: int) -> list[dict[str, Any]]:
        """旧诊断记录回查：返回该视图记录的全部历史快照。"""
        return store.get_versions(MODULE, entry_id)

    @staticmethod
    def _row_sort_key(row: dict[str, Any]) -> tuple:
        return (
            str(row.get("表名称", "")),
            version_sort_key(row.get("定义版本")),
            str(row.get("版本来源", "")),
        )

    # ---- 汇总（概览看板）----

    def summary(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        current = [row for row in rows if row.get("是否当前") == "是"]
        conflicts = [row for row in rows if row.get("冲突标记") == "版本冲突"]
        return {
            "覆盖表数": len({str(row.get("表名称", "")) for row in rows if row.get("表名称")}),
            "版本记录数": len(rows),
            "手工当前数": sum(1 for row in current if row.get("当前来源") == SOURCE_MANUAL),
            "血缘当前数": sum(1 for row in current if row.get("当前来源") == SOURCE_DERIVED),
            "版本冲突数": len({(row.get("表名称"), row.get("定义版本")) for row in conflicts}),
            "未完成数": sum(1 for row in rows if row.get("记录状态") != "已完成"),
            "最近业务日期": max((str(row.get("业务日期", "")) for row in rows), default=""),
        }

    # ---- 结构注册/血缘推导入口：先写未完成占位 ----

    def mark_unfinished(self, schema_entry: dict[str, Any]) -> dict[str, Any] | None:
        """结构定义登记后写入未完成占位；同键已完成的记录重新标记为待补全。"""
        table = str(schema_entry.get("表名称") or "").strip()
        version = str(schema_entry.get("定义版本") or "").strip()
        if not table or not version:
            return None
        source = entry_source(schema_entry)
        rows = store.rows(MODULE)
        for row in rows:
            if (
                row.get("表名称") == table
                and row.get("定义版本") == version
                and row.get("版本来源") == source
            ):
                if row.get("记录状态") == "已完成":
                    row["记录状态"] = "未完成"
                    row["pending"] = True
                    store.save_version(MODULE, int(row.get("id", 0)), row)
                return row
        row = {
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "视图编号": view_code(table, version, source),
            "表名称": table,
            "定义版本": version,
            "版本序号": _version_number(version),
            "自然顺序": 0,
            "是否当前": "否",
            "版本来源": source,
            "当前来源": "",
            "冲突标记": "无冲突",
            "冲突处理": "",
            "业务日期": entry_business_date(schema_entry),
            "跨月标记": "否",
            "记录状态": "未完成",
            "来源模块": SOURCE_MODULE.get(source, "schema_registry"),
            "来源定义编号": str(schema_entry.get("定义编号") or ""),
            "调用链": "",
            "生成时间": datetime.now().isoformat(),
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(row)
        return row

    # ---- 刷新：只续写未完成部分，并核对排序与当前引用一致 ----

    def refresh(self, table_name: str | None = None, business_date: str | None = None) -> dict[str, int]:
        """增量刷新诊断视图。

        - 已完成的记录不重写，只补全新增版本与未完成占位；
        - 每次刷新对目标表做全量一致性核对（自然顺序/是否当前/当前来源/冲突标记）。
        """
        schema_service = SchemaRegistryService()
        biz_date = (business_date or "").strip() or date.today().isoformat()
        if table_name:
            tables = [table_name]
        else:
            tables = sorted({
                str(entry.get("表名称") or "").strip()
                for entry in store.rows("schema_registry")
                if str(entry.get("表名称") or "").strip()
            })
        stats = {"刷新表数": 0, "新建记录": 0, "续写完成": 0, "一致性修正": 0}
        for table in tables:
            result = self._refresh_table(table, schema_service, biz_date)
            stats["刷新表数"] += 1
            stats["新建记录"] += result["新建记录"]
            stats["续写完成"] += result["续写完成"]
            stats["一致性修正"] += result["一致性修正"]
        return stats

    def _refresh_table(
        self,
        table: str,
        schema_service: SchemaRegistryService,
        biz_date: str,
    ) -> dict[str, int]:
        rows = store.rows(MODULE)
        entries = [
            entry for entry in schema_service.get_schema_for_table(table)
            if entry.get("status") != "已废弃"
        ]
        # 同（定义版本, 版本来源）多份定义时取 id 最大者作为代表
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in entries:
            key = (str(entry.get("定义版本") or ""), entry_source(entry))
            if key not in groups or int(entry.get("id", 0)) > int(groups[key].get("id", 0)):
                groups[key] = entry
        existing = {
            (str(row.get("定义版本") or ""), str(row.get("版本来源") or "")): row
            for row in rows
            if row.get("表名称") == table
        }
        created = 0
        completed = 0
        for (version, source), entry in groups.items():
            row = existing.get((version, source))
            if row is not None and row.get("记录状态") == "已完成":
                continue  # 已完成部分不重写
            payload = self._diagnose_payload(table, entry, biz_date)
            if row is None:
                row = {
                    "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
                    "视图编号": payload["视图编号"],
                    "表名称": table,
                    "定义版本": version,
                    "版本来源": source,
                    "自然顺序": 0,
                    "是否当前": "否",
                    "当前来源": "",
                    "冲突标记": "无冲突",
                    "冲突处理": "",
                    "跨月标记": "否",
                    **{k: v for k, v in payload.items() if k != "视图编号"},
                    "记录状态": "已完成",
                    "status": STATUS_ORDER[0],
                    "pending": False,
                    "abnormal": False,
                }
                rows.append(row)
                created += 1
            else:
                row.update(payload)
                row["记录状态"] = "已完成"
                row["pending"] = False
                store.save_version(MODULE, int(row.get("id", 0)), row)
                completed += 1
        reconciled = self._reconcile_table(table, schema_service, biz_date)
        return {"新建记录": created, "续写完成": completed, "一致性修正": reconciled}

    def _diagnose_payload(self, table: str, entry: dict[str, Any], biz_date: str) -> dict[str, Any]:
        source = entry_source(entry)
        if source == SOURCE_DERIVED:
            edge_sources = list(store.get_lineage_edges()) + list(store.rows("lineage_track"))
            upstream = next(
                (
                    str(edge.get("上游表名", ""))
                    for edge in edge_sources
                    if edge.get("下游表名") == table and edge.get("上游表名")
                ),
                "",
            )
            call_chain = f"血缘推导←{upstream}" if upstream else "血缘推导"
        else:
            call_chain = "结构注册入口"
        return {
            "视图编号": view_code(table, str(entry.get("定义版本") or ""), source),
            "版本序号": _version_number(entry.get("定义版本")),
            "业务日期": entry_business_date(entry, biz_date),
            "来源模块": SOURCE_MODULE.get(source, "schema_registry"),
            "来源定义编号": str(entry.get("定义编号") or ""),
            "调用链": call_chain,
            "生成时间": datetime.now().isoformat(),
        }

    def _reconcile_table(
        self,
        table: str,
        schema_service: SchemaRegistryService,
        biz_date: str,
    ) -> int:
        """核对单表的排序与当前引用：与 resolve_current_entry 的解析结果一致落库。"""
        rows = [row for row in store.rows(MODULE) if row.get("表名称") == table]
        if not rows:
            return 0
        resolution = schema_service.resolve_current_entry(table, biz_date)
        current_version = resolution["当前版本"] if resolution else ""
        current_source = resolution["当前来源"] if resolution else ""
        conflict = resolution["冲突"] if resolution else None
        ordered = sorted(rows, key=self._row_sort_key)
        changed = 0
        for rank, row in enumerate(ordered, start=1):
            is_current = (
                str(row.get("定义版本") or "") == current_version
                and str(row.get("版本来源") or "") == current_source
            )
            in_conflict = bool(conflict) and str(row.get("定义版本") or "") == conflict.get("冲突版本")
            if in_conflict:
                conflict_flag = "版本冲突"
                cross_month = str(conflict.get("跨月标记") or "否")
                handling = "" if is_current else str(conflict.get("处理") or "")
            else:
                conflict_flag = "无冲突"
                cross_month = "否"
                handling = ""
            updates = {
                "自然顺序": rank,
                "是否当前": "是" if is_current else "否",
                "当前来源": current_source,
                "冲突标记": conflict_flag,
                "冲突处理": handling,
                "跨月标记": cross_month,
            }
            dirty = False
            for field, value in updates.items():
                if row.get(field) != value:
                    row[field] = value
                    dirty = True
            abnormal = conflict_flag == "版本冲突"
            if row.get("abnormal") != abnormal:
                row["abnormal"] = abnormal
                dirty = True
            if dirty:
                store.save_version(MODULE, int(row.get("id", 0)), row)
                changed += 1
        return changed

    # ---- 动作 ----

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"诊断视图记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于结构版本诊断视图可执行范围"
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.save_version(MODULE, entry_id, entry)
        return entry, f"诊断视图记录已{action}"
