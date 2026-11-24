"""书源的存取（数据库 <-> SourceRules），API 层只调这里。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import SEED_DIR
from .engine.source import SourceRules, parse_source
from .models import BookSource


def upsert_source(db: Session, data: dict[str, Any]) -> tuple[BookSource, bool]:
    """按 bookSourceUrl 新增或覆盖。返回 (记录, 是否新建)。"""
    rules = parse_source(data)  # 校验
    row = db.scalar(select(BookSource).where(BookSource.source_url == rules.source_url))
    created = row is None
    if created:
        row = BookSource(source_url=rules.source_url)
        db.add(row)
    fill_row(row, rules, data)
    return row, created


def fill_row(row: BookSource, rules: SourceRules, data: dict[str, Any]) -> None:
    row.source_url = rules.source_url
    row.name = rules.name
    row.group_name = rules.group
    row.source_type = rules.type
    row.format = rules.format
    row.enabled = rules.enabled
    row.weight = rules.weight
    row.sort_order = rules.order
    row.remark = rules.remark
    row.raw_json = json.dumps(data, ensure_ascii=False)


def set_enabled(row: BookSource, enabled: bool) -> None:
    """启用状态同时写回 raw_json，保证导出时一致。"""
    row.enabled = enabled
    data = json.loads(row.raw_json)
    data["enable" if row.format == "legacy" else "enabled"] = enabled
    row.raw_json = json.dumps(data, ensure_ascii=False)


_cache: dict[int, tuple[int, SourceRules]] = {}


def rules_of(row: BookSource) -> SourceRules:
    """解析结果按 raw_json 内容缓存，书源被修改后自动失效。"""
    key = hash(row.raw_json)
    hit = _cache.get(row.id)
    if hit and hit[0] == key:
        return hit[1]
    rules = parse_source(json.loads(row.raw_json))
    _cache[row.id] = (key, rules)
    return rules


def seed_if_empty(db: Session) -> int:
    if db.scalar(select(BookSource.id).limit(1)) is not None:
        return 0
    n = 0
    for p in sorted(Path(SEED_DIR).glob("*.json")):
        data = json.loads(p.read_text("utf-8"))
        for item in data if isinstance(data, list) else [data]:
            upsert_source(db, item)
            n += 1
    db.commit()
    return n
