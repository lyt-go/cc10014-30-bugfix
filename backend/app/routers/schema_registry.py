"""结构注册接口：维护结构定义，覆盖提交校验、标记生效、标记废弃等动作。"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import ActionPayload, ActionResult, EntryPayload, PageResult
from app.services.schema_registry import SchemaRegistryService

router = APIRouter(prefix="/api/schema_registry", tags=["结构注册"])

service = SchemaRegistryService()

LIST_FIELDS = ["定义编号", "表名称", "字段名称", "字段类型", "可空标识", "默认值", "定义版本", "生效批次"]
STATUSES = ["草稿", "待校验", "已生效", "已废弃"]


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
    keyword: str | None = Query(default=None, description="按定义编号检索"),
    status: str | None = Query(default=None, description="草稿、待校验、已生效、已废弃"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    """按页面字段、定义编号关键字与状态过滤结构注册列表。"""
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
    output.write("\ufeff")
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
        headers={"Content-Disposition": 'attachment; filename="schema_registry.csv"'})


@router.get("/current/{table_name}", response_model=dict)
def get_current_schema(table_name: str) -> dict:
    """按语义版本解析同名表的当前结构，结果与结构版本诊断视图一致。"""
    resolution = service.resolve_current_entry(table_name)
    if resolution is None:
        raise HTTPException(status_code=404, detail=f"表 {table_name} 暂无结构定义")
    return resolution


@router.post("/derive/{table_name}", response_model=ActionResult)
def derive_schema(table_name: str, payload: dict[str, object] | None = None) -> ActionResult:
    """按血缘链路推导同名表的下一个结构版本，版本号基于语义版本递增。"""
    business_date = str((payload or {}).get("业务日期") or "").strip() or None
    entry = service.derive_schema_from_lineage(table_name, business_date=business_date)
    if entry is None:
        return ActionResult(ok=False, message=f"表 {table_name} 缺少上游血缘或上游结构，无法推导")
    return ActionResult(ok=True, message=f"已按血缘推导结构版本 {entry.get('定义版本')}", entry=entry)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条结构定义明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"结构定义 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: dict[str, object]) -> ActionResult:
    """登记一条结构定义，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="结构定义已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """对单条结构定义执行提交校验、标记生效、标记废弃；不允许的动作会被拦下并说明原因。"""
    entry, message = service.run_action(entry_id, payload.action.strip())
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
