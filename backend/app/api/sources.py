"""书源管理：列表 / 导入（JSON 或 URL）/ 查看原始 JSON / 修改 / 启停 / 删除。"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine.request import Req, fetch
from ..engine.source import SourceFormatError, parse_source
from ..models import BookSource
from ..schemas import EnabledIn, ImportResult, ImportUrlIn, SourceOut
from ..services import fill_row, set_enabled, upsert_source

router = APIRouter(prefix="/api/sources", tags=["sources"])


def get_row(db: Session, source_id: int) -> BookSource:
    row = db.get(BookSource, source_id)
    if row is None:
        raise HTTPException(404, "书源不存在")
    return row


@router.get("", response_model=list[SourceOut])
def list_sources(type: str | None = None, enabled: bool | None = None, db: Session = Depends(get_db)):
    q = select(BookSource)
    if type:
        q = q.where(BookSource.source_type == type)
    if enabled is not None:
        q = q.where(BookSource.enabled == enabled)
    q = q.order_by(BookSource.sort_order, BookSource.weight.desc(), BookSource.id)
    return db.scalars(q).all()


def _import(db: Session, payload: Any) -> ImportResult:
    items = payload if isinstance(payload, list) else [payload]
    created = updated = 0
    errors: list[str] = []
    rows: list[BookSource] = []
    for i, item in enumerate(items):
        try:
            row, is_new = upsert_source(db, item)
            db.flush()
            rows.append(row)
            created += is_new
            updated += not is_new
        except (SourceFormatError, ValueError, TypeError) as e:
            errors.append(f"第 {i + 1} 条: {e}")
    db.commit()
    return ImportResult(created=created, updated=updated, errors=errors, sources=rows)


@router.post("", response_model=ImportResult)
def import_sources(payload: Any = Body(..., description="单个书源对象或书源数组"), db: Session = Depends(get_db)):
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"JSON 解析失败: {e}") from e
    return _import(db, payload)


@router.post("/import-url", response_model=ImportResult)
async def import_from_url(body: ImportUrlIn, db: Session = Depends(get_db)):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "只支持 http/https 地址")
    resp = await fetch(Req(url=body.url, headers={"User-Agent": "Mozilla/5.0"}))
    try:
        payload = json.loads(resp.text)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"远程内容不是 JSON: {e}") from e
    return _import(db, payload)


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_db)):
    return get_row(db, source_id)


@router.get("/{source_id}/json")
def get_source_json(source_id: int, db: Session = Depends(get_db)):
    return json.loads(get_row(db, source_id).raw_json)


@router.put("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    row = get_row(db, source_id)
    try:
        rules = parse_source(payload)
    except SourceFormatError as e:
        raise HTTPException(400, str(e)) from e
    if rules.source_url != row.source_url:
        clash = db.scalar(select(BookSource).where(BookSource.source_url == rules.source_url))
        if clash is not None:
            raise HTTPException(409, "已存在相同 bookSourceUrl 的书源")
    fill_row(row, rules, payload)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{source_id}/enabled", response_model=SourceOut)
def toggle_source(source_id: int, body: EnabledIn, db: Session = Depends(get_db)):
    row = get_row(db, source_id)
    set_enabled(row, body.enabled)
    db.commit()
    return row


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    db.delete(get_row(db, source_id))
    db.commit()
    return {"ok": True}
