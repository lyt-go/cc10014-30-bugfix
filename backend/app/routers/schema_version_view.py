"""结构版本诊断视图接口：自然版本顺序列表、增量刷新、汇总与历史回查。"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import ActionPayload, ActionResult, PageResult
from app.services.schema_version_view import SchemaVersionViewService

router = APIRouter(prefix="/api/schema_version_view", tags=["结构版本诊断视图"])

service = SchemaVersionViewService()

LIST_FIELDS = [
    "视图编号", "表名称", "定义版本", "自然顺序", "是否当前", "版本来源",
    "当前来源", "冲突标记", "冲突处理", "业务日期", "跨月标记", "记录状态",
]
STATUSES = ["待确认", "已复核"]


def query_filters(request: Request) -> dict[str, str]:
    """只接受当前模块声明过的字段，忽略分页等保留参数。"""
    return {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in LIST_FIELDS and value.strip()
    }


@router.get("", response_model=PageResult[dict])
def list_entries(
    request: Request,
    keyword: str | None = Query(default=None, description="按视图编号检索"),
    status: str | None = Query(default=None, description="待确认、已复核"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    """按页面字段、视图编号关键字与状态过滤诊断视图，结果按自然版本顺序返回。"""
    items, total = service.list_entries(
        filters=query_filters(request), keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> StreamingResponse:
    """下载当前筛选条件下的 UTF-8 CSV；必须声明在 /{entry_id} 之前。"""
    items, _ = service.list_entries(
        filters=query_filters(request), keyword=keyword, status=status, page=1, size=1000000)
    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id", *LIST_FIELDS, "status"])
    for item in items:
        row = []
        for value in [item.get("id"), *(item.get(field, "") for field in LIST_FIELDS), item.get("status", "")]:
            text = "" if value is None else str(value)
            row.append("'" + text if text.startswith(("=", "+", "-", "@")) else text)
        writer.writerow(row)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="schema_version_view.csv"'})


@router.get("/summary")
def view_summary() -> dict:
    """诊断视图汇总：覆盖表数、当前来源分布、冲突与未完成量，供概览看板展示。"""
    return service.summary()


@router.post("/refresh", response_model=ActionResult)
def refresh_view(payload: dict[str, object] | None = None) -> ActionResult:
    """增量刷新诊断视图：只续写未完成部分，并核对版本排序与当前引用一致落库。"""
    payload = payload or {}
    table_name = str(payload.get("表名称") or "").strip() or None
    business_date = str(payload.get("业务日期") or "").strip() or None
    stats = service.refresh(table_name=table_name, business_date=business_date)
    message = (
        f"结构版本诊断视图已刷新：表 {stats['刷新表数']} 个，新建 {stats['新建记录']} 条，"
        f"续写 {stats['续写完成']} 条，一致性修正 {stats['一致性修正']} 处"
    )
    return ActionResult(ok=True, message=message, entry=stats)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条诊断视图记录；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"诊断视图记录 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/history")
def get_history(entry_id: int) -> dict:
    """旧诊断记录回查：返回该记录的全部历史快照。"""
    if service.get_entry(entry_id) is None:
        raise HTTPException(status_code=404, detail=f"诊断视图记录 {entry_id} 不存在或已归档")
    return {"items": service.get_history(entry_id)}


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """对单条诊断记录执行标记复核；不允许的动作会被拦下并说明原因。"""
    entry, message = service.run_action(entry_id, payload.action.strip())
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
