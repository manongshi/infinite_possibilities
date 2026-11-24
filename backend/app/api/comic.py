"""漫画浏览：发现 / 搜索 / 详情 / 目录 / 正文图片 / 图片代理。

接口按 source_id + url 定位，不落库；以后加书架、阅读记录时再加表。
"""
from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine import book
from ..engine.js import JsError
from ..engine.request import FetchError, client
from ..engine.rule import RuleError
from ..engine.source import SourceRules, image_headers
from ..models import BookSource
from ..services import rules_of
from .sources import get_row

router = APIRouter(prefix="/api", tags=["comic"])

SEARCH_TIMEOUT = 25


def _rules(db: Session, source_id: int) -> SourceRules:
    return rules_of(get_row(db, source_id))


async def _guard(coro):
    try:
        return await coro
    except (FetchError, RuleError, JsError) as e:
        raise HTTPException(502, str(e)) from e


@router.get("/sources/{source_id}/explore")
def explore_kinds(source_id: int, db: Session = Depends(get_db)):
    return book.to_dict(book.explore_kinds(_rules(db, source_id)))


@router.get("/sources/{source_id}/explore/books")
async def explore_books(source_id: int, url: str, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    items, more = await _guard(book.explore(_rules(db, source_id), url, page))
    return {"page": page, "has_more": more, "items": book.to_dict(items)}


@router.get("/search")
async def search(
    keyword: str = Query(..., min_length=1),
    source_id: int | None = None,
    source_type: str = Query("comic", alias="type"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """不传 source_id 时并发搜索所有启用的同类型书源。"""
    if source_id is not None:
        rows = [get_row(db, source_id)]
    else:
        rows = list(
            db.scalars(
                select(BookSource)
                .where(BookSource.enabled.is_(True), BookSource.source_type == source_type)
                .order_by(BookSource.sort_order, BookSource.weight.desc())
            )
        )

    async def one(row: BookSource):
        try:
            items = await asyncio.wait_for(book.search(rules_of(row), keyword, page), SEARCH_TIMEOUT)
            return {"source_id": row.id, "source_name": row.name, "items": book.to_dict(items), "error": None}
        except Exception as e:  # noqa: BLE001  单个源失败不影响其他源
            return {"source_id": row.id, "source_name": row.name, "items": [], "error": str(e) or type(e).__name__}

    return {"keyword": keyword, "page": page, "results": await asyncio.gather(*(one(r) for r in rows))}


@router.get("/sources/{source_id}/book")
async def book_info(source_id: int, url: str, db: Session = Depends(get_db)):
    return book.to_dict(await _guard(book.book_info(_rules(db, source_id), url)))


@router.get("/sources/{source_id}/chapters")
async def chapters(source_id: int, url: str, db: Session = Depends(get_db)):
    """url 传详情接口返回的 toc_url。"""
    return book.to_dict(await _guard(book.chapter_list(_rules(db, source_id), url)))


@router.get("/sources/{source_id}/content")
async def content(source_id: int, url: str, next_url: str = "", db: Session = Depends(get_db)):
    c = await _guard(book.content(_rules(db, source_id), url, next_url))
    return book.to_dict(c)


@router.get("/image")
async def image_proxy(
    url: str,
    source_id: int | None = None,
    headers: str | None = Query(None, description="JSON 对象，覆盖默认图片请求头"),
    db: Session = Depends(get_db),
):
    """图片代理：带上书源要求的 Referer/UA，App 端不用关心防盗链。以后图片解密也放这里。"""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "非法图片地址")
    h: dict[str, str] = {}
    if source_id is not None:
        row = db.get(BookSource, source_id)
        if row is not None:
            h.update(image_headers(rules_of(row)))
    if headers:
        try:
            h.update({str(k): str(v) for k, v in json.loads(headers).items()})
        except (json.JSONDecodeError, AttributeError) as e:
            raise HTTPException(400, "headers 不是合法 JSON 对象") from e
    try:
        r = await client().get(url, headers=h)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"图片获取失败: {e!r}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, "图片获取失败")
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg").split(";")[0],
        headers={"Cache-Control": "public, max-age=604800"},
    )
