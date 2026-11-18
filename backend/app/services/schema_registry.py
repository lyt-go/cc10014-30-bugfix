"""结构定义业务规则：管理表的字段结构，版本化管理。

同名表的结构版本按语义版本（自然顺序）比较：v9 < v10，不再按字符串排序。
当前版本解析结果与结构版本诊断视图共用同一套逻辑，保证落库一致。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.store import store

MODULE = "schema_registry"
LIST_FIELDS = ["定义编号", "表名称", "字段名称", "字段类型", "可空标识", "默认值", "定义版本", "生效批次"]
REQUIRED_FIELDS = ["定义编号", "表名称", "字段名称"]
STATUS_ORDER = ["草稿", "待校验", "已生效", "已废弃"]
ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "标记废弃": "已废弃"}
NEGATIVE_ACTIONS = []

SOURCE_MANUAL = "手工"
SOURCE_DERIVED = "血缘推导"
DERIVED_CODE_PREFIX = "SCH-DERIVED"


def version_sort_key(version: object) -> tuple:
    """把定义版本解析成可比较的自然顺序键：v9 < v10、v1 < v1.1。

    返回 (数字段元组, 原文) 两级键，保证纯字符串版本也有确定顺序。
    """
    text = str(version or "").strip()
    nums = tuple(int(n) for n in re.findall(r"\d+", text))
    return (nums, text)


def next_version(current: object) -> str:
    """在现有版本号上递增末位数字：v9 -> v10、v10 -> v11、v1.2 -> v1.3。"""
    text = str(current or "").strip()
    matches = list(re.finditer(r"\d+", text))
    if not matches:
        return "v1"
    last = matches[-1]
    return text[:last.start()] + str(int(last.group()) + 1) + text[last.end():]


def entry_source(entry: dict[str, Any]) -> str:
    """判断结构定义来源：手工登记 或 血缘推导。"""
    source = str(entry.get("版本来源") or "").strip()
    if source:
        return source
    code = str(entry.get("定义编号") or "")
    return SOURCE_DERIVED if code.startswith(DERIVED_CODE_PREFIX) else SOURCE_MANUAL


def entry_business_date(entry: dict[str, Any], fallback: str = "") -> str:
    """取结构定义的业务日期：优先显式业务日期，其次从生效批次解析，最后回退到给定日期。"""
    biz = str(entry.get("业务日期") or "").strip()
    if biz:
        return biz[:10]
    batch = str(entry.get("生效批次") or "")
    match = re.search(r"(\d{4})(\d{2})(\d{2})", batch)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return fallback or date.today().isoformat()


class SchemaRegistryService:
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
            rows = [row for row in rows if keyword.casefold() in str(row.get("定义编号", "")).casefold()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in LIST_FIELDS})
        entry["版本来源"] = str(values.get("版本来源") or "").strip() or SOURCE_MANUAL
        entry["业务日期"] = str(values.get("业务日期") or "").strip() or entry_business_date(entry)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        # 结构注册入口 → 结构版本诊断视图：先写未完成占位，刷新结构时补全诊断内容
        from app.services.schema_version_view import SchemaVersionViewService
        SchemaVersionViewService().mark_unfinished(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"结构定义 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于结构注册可执行范围"
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.save_version(MODULE, entry_id, entry)
        return entry, f"结构定义已{action}"

    def get_schema_for_table(self, table_name: str) -> list[dict[str, Any]]:
        return store.find_all_by_field(MODULE, "表名称", table_name)

    def resolve_current_entry(self, table_name: str, business_date: str | None = None) -> dict[str, Any] | None:
        """按语义版本解析同名表的当前结构，与结构版本诊断视图保持一致。

        同版本号出现手工与血缘推导两份定义时按业务日期判定边界：
        - 较窄边界（同一业务月份）：手工版本为当前版本，推导版本记为推导候选；
        - 较宽边界（跨业务月份）：推导版本为当前版本，手工版本记为手工审核差异。
        """
        candidates = [
            entry for entry in self.get_schema_for_table(table_name)
            if entry.get("status") != STATUS_ORDER[-1]
        ]
        if not candidates:
            return None
        top_key = max(version_sort_key(entry.get("定义版本")) for entry in candidates)
        top = [entry for entry in candidates if version_sort_key(entry.get("定义版本")) == top_key]
        manual = sorted(
            (entry for entry in top if entry_source(entry) == SOURCE_MANUAL),
            key=lambda entry: int(entry.get("id", 0)),
        )
        derived = sorted(
            (entry for entry in top if entry_source(entry) == SOURCE_DERIVED),
            key=lambda entry: int(entry.get("id", 0)),
        )
        conflict = None
        if manual and derived:
            manual_entry, derived_entry = manual[-1], derived[-1]
            manual_biz = entry_business_date(manual_entry, business_date or "")
            derived_biz = entry_business_date(derived_entry, business_date or "")
            cross_month = manual_biz[:7] != derived_biz[:7]
            if cross_month:
                current, source = derived_entry, SOURCE_DERIVED
                conflict = {
                    "边界": "较宽边界",
                    "跨月标记": "是",
                    "冲突版本": str(current.get("定义版本") or ""),
                    "当前侧定义编号": str(derived_entry.get("定义编号") or ""),
                    "差异侧定义编号": str(manual_entry.get("定义编号") or ""),
                    "处理": "手工审核差异",
                    "手工业务日期": manual_biz,
                    "推导业务日期": derived_biz,
                }
            else:
                current, source = manual_entry, SOURCE_MANUAL
                conflict = {
                    "边界": "较窄边界",
                    "跨月标记": "否",
                    "冲突版本": str(current.get("定义版本") or ""),
                    "当前侧定义编号": str(manual_entry.get("定义编号") or ""),
                    "差异侧定义编号": str(derived_entry.get("定义编号") or ""),
                    "处理": "推导候选",
                    "手工业务日期": manual_biz,
                    "推导业务日期": derived_biz,
                }
        else:
            ordered = sorted(top, key=lambda entry: int(entry.get("id", 0)))
            current = ordered[-1]
            source = entry_source(current)
        return {
            "表名称": table_name,
            "entry": current,
            "当前版本": str(current.get("定义版本") or ""),
            "当前来源": source,
            "冲突": conflict,
        }

    def get_latest_schema(self, table_name: str) -> dict[str, Any] | None:
        resolution = self.resolve_current_entry(table_name)
        return resolution["entry"] if resolution else None

    def derive_schema_from_lineage(self, table_name: str, business_date: str | None = None) -> dict[str, Any] | None:
        """从血缘关系推导字段变更：找上游表最新schema并合并。

        下一个推导版本基于语义版本解析出的当前版本递增，避免与手工版本撞号。
        """
        # 查找血缘中该table_name作为下游的边：自动采集的血缘边 + 血缘追踪模块登记的链路
        upstream_tables = []
        edge_sources = list(store.get_lineage_edges()) + list(store.rows("lineage_track"))
        for edge in edge_sources:
            if edge.get("下游表名") == table_name:
                up = edge.get("上游表名", "")
                if up and up not in upstream_tables:
                    upstream_tables.append(up)
        if not upstream_tables:
            return None
        # 取第一个上游的最新schema
        up_schema = self.get_latest_schema(upstream_tables[0])
        if not up_schema:
            return None
        resolution = self.resolve_current_entry(table_name, business_date)
        new_version = next_version(resolution["当前版本"]) if resolution else "v1"
        # 生成新schema定义
        new_entry = {
            "定义编号": f"{DERIVED_CODE_PREFIX}-{table_name}-{new_version}",
            "表名称": table_name,
            "字段名称": up_schema.get("字段名称", ""),
            "字段类型": up_schema.get("字段类型", ""),
            "可空标识": up_schema.get("可空标识", ""),
            "默认值": up_schema.get("默认值", ""),
            "定义版本": new_version,
            "生效批次": up_schema.get("生效批次", ""),
            "版本来源": SOURCE_DERIVED,
            "业务日期": (business_date or "").strip() or date.today().isoformat(),
        }
        return self.create_entry(new_entry)[0]
