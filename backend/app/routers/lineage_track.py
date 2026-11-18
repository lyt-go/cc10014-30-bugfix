"""血缘追踪 DAG 拓扑接口：返回节点、连线图结构。"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import ActionPayload, ActionResult, EntryPayload, PageResult
from app.services.lineage_track import LineageTrackService

router = APIRouter(prefix="/api/lineage_track", tags=["血缘追踪"])
service = LineageTrackService()
LIST_FIELDS = ["链路编号", "上游表名", "下游表名", "来源字段", "目标字段", "转换逻辑", "采集批次", "链路版本"]
STATUSES = ["草稿", "待校验", "已生效", "已停用"]


def csv_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    if text and text[0] in "=+-@":
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


@router.get("")
def get_graph() -> dict[str, Any]:
    """返回节点与边组成的 DAG 图数据。"""
    return service.get_graph()


@router.get("/export")
def export_entries() -> StreamingResponse:
    nodes, edges = service.raw_data()
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["type", "id", "name", "from", "to", "label", "status"])
    for node in nodes:
        writer.writerow(["node", node.get("id",""), csv_cell(node.get("name","")), "", "", "", node.get("status","")])
    for edge in edges:
        writer.writerow(["edge", "", "", edge.get("from",""), edge.get("to",""), edge.get("label",""), ""])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=lineage_track.csv"})


@router.get("/schema_view/{table_name}")
def schema_view_for_table(table_name: str) -> dict[str, Any]:
    """血缘详情联动：按表名读取结构版本诊断视图与当前版本解析结果。"""
    from app.services.schema_registry import SchemaRegistryService
    from app.services.schema_version_view import SchemaVersionViewService
    resolution = SchemaRegistryService().resolve_current_entry(table_name)
    return {
        "表名称": table_name,
        "当前版本": resolution["当前版本"] if resolution else "",
        "当前来源": resolution["当前来源"] if resolution else "",
        "冲突": resolution["冲突"] if resolution else None,
        "items": SchemaVersionViewService().list_for_table(table_name),
    }


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict:
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"血缘链路 {entry_id} 不存在")
    return entry


@router.post("")
def create_entry(payload: EntryPayload) -> ActionResult:
    entry_or_none, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="血缘链路已登记", entry=entry_or_none)


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    entry_or_none, message = service.run_action(entry_id, payload.action)
    if entry_or_none is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry_or_none)


@router.post("/auto-generate")
def auto_generate() -> dict[str, Any]:
    """从转换编排节点自动生成血缘关系。"""
    result = service.auto_generate_from_transform()
    return result
