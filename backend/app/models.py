"""数据库表。

book_sources：一条记录 = 一个书源。raw_json 原样保存导入的书源 JSON（不丢字段，
兼容旧版「阅读」平铺格式和 Legado 3 嵌套格式）；其余列只是为了列表/筛选冗余出来的索引字段。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class BookSource(Base):
    __tablename__ = "book_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    group_name: Mapped[str] = mapped_column(String(255), default="")
    # comic / text / audio / file —— 目前 App 只用 comic
    source_type: Mapped[str] = mapped_column(String(16), default="text", index=True)
    # legacy（旧版平铺 ruleXxx 字段）/ legado（Legado 3 嵌套 ruleSearch 等）
    format: Mapped[str] = mapped_column(String(16), default="legado")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
