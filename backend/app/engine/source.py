"""书源模型：把两种书源 JSON 统一成同一个内部结构。

* legacy：旧版「阅读」/ MyBookshelf 的平铺格式（ruleSearchUrl、ruleSearchList、ruleBookContent…）
* legado：Legado 3 的嵌套格式（searchUrl、ruleSearch{bookList,…}、ruleContent{content,…}）

后面的解析流水线只认 SourceRules，不关心原始格式。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..config import DEFAULT_UA


class SourceFormatError(ValueError):
    pass


@dataclass
class ListRule:
    book_list: str = ""
    name: str = ""
    author: str = ""
    kind: str = ""
    intro: str = ""
    last_chapter: str = ""
    update_time: str = ""
    cover_url: str = ""
    book_url: str = ""
    word_count: str = ""
    next_url: str = ""


@dataclass
class InfoRule:
    init: str = ""
    name: str = ""
    author: str = ""
    kind: str = ""
    intro: str = ""
    last_chapter: str = ""
    update_time: str = ""
    cover_url: str = ""
    toc_url: str = ""
    word_count: str = ""


@dataclass
class TocRule:
    chapter_list: str = ""
    chapter_name: str = ""
    chapter_url: str = ""
    next_toc_url: str = ""
    update_time: str = ""
    is_volume: str = ""


@dataclass
class ContentRule:
    content: str = ""
    next_content_url: str = ""
    title: str = ""
    image_style: str = ""
    replace_regex: str = ""


@dataclass
class SourceRules:
    source_url: str
    name: str
    group: str = ""
    type: str = "text"  # text / comic / audio / file
    format: str = "legado"
    enabled: bool = True
    weight: int = 0
    order: int = 0
    remark: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    charset: str = ""
    js_lib: str = ""
    search_url: str = ""
    explore_url: str = ""
    book_url_pattern: str = ""
    search: ListRule = field(default_factory=ListRule)
    explore: ListRule = field(default_factory=ListRule)
    info: InfoRule = field(default_factory=InfoRule)
    toc: TocRule = field(default_factory=TocRule)
    content: ContentRule = field(default_factory=ContentRule)

    @property
    def base_url(self) -> str:
        # Legado 允许 bookSourceUrl 带 "#备注" 后缀
        return self.source_url.split("#", 1)[0].rstrip("/")


_TYPE_MAP_INT = {0: "text", 1: "audio", 2: "comic", 3: "file"}
_TYPE_MAP_STR = {
    "漫画": "comic", "图片": "comic", "comic": "comic", "image": "comic",
    "音频": "audio", "有声": "audio", "audio": "audio",
    "文件": "file", "file": "file",
    "文本": "text", "小说": "text", "text": "text", "": "text",
}


def _s(v: Any) -> str:
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def _obj(v: Any) -> dict:
    """规则对象既可能是 dict，也可能是 JSON 字符串。"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip().startswith("{"):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_headers(v: Any) -> dict[str, str]:
    if isinstance(v, dict):
        return {str(k): _s(x) for k, x in v.items()}
    if isinstance(v, str) and v.strip():
        t = v.strip()
        if t.startswith("@js:") or t.startswith("<js>"):
            return {}  # JS 生成的 header 暂不支持
        try:
            d = json.loads(t)
            if isinstance(d, dict):
                return {str(k): _s(x) for k, x in d.items()}
        except json.JSONDecodeError:
            pass
    return {}


def _source_type(v: Any) -> str:
    if isinstance(v, bool):
        return "text"
    if isinstance(v, int):
        return _TYPE_MAP_INT.get(v, "text")
    s = _s(v).strip()
    if s.isdigit():
        return _TYPE_MAP_INT.get(int(s), "text")
    return _TYPE_MAP_STR.get(s.lower(), _TYPE_MAP_STR.get(s, "text"))


def detect_format(d: dict) -> str:
    if any(k in d for k in ("ruleSearchUrl", "ruleSearchList", "ruleBookContent", "ruleChapterList")):
        return "legacy"
    return "legado"


def parse_source(d: dict) -> SourceRules:
    if not isinstance(d, dict):
        raise SourceFormatError("书源必须是 JSON 对象")
    url = _s(d.get("bookSourceUrl")).strip()
    name = _s(d.get("bookSourceName")).strip()
    if not url or not name:
        raise SourceFormatError("书源缺少 bookSourceUrl 或 bookSourceName")
    fmt = detect_format(d)
    return _parse_legacy(d, url, name) if fmt == "legacy" else _parse_legado(d, url, name)


def _parse_legacy(d: dict, url: str, name: str) -> SourceRules:
    headers: dict[str, str] = {}
    if _s(d.get("httpUserAgent")).strip():
        headers["User-Agent"] = _s(d["httpUserAgent"]).strip()
    search = ListRule(
        book_list=_s(d.get("ruleSearchList")),
        name=_s(d.get("ruleSearchName")),
        author=_s(d.get("ruleSearchAuthor")),
        kind=_s(d.get("ruleSearchKind")),
        intro=_s(d.get("ruleSearchIntroduce")),
        last_chapter=_s(d.get("ruleSearchLastChapter")),
        cover_url=_s(d.get("ruleSearchCoverUrl")),
        book_url=_s(d.get("ruleSearchNoteUrl")),
        next_url=_s(d.get("ruleSearchUrlNext")),
    )
    return SourceRules(
        source_url=url,
        name=name,
        group=_s(d.get("bookSourceGroup")),
        type=_source_type(d.get("bookSourceType")),
        format="legacy",
        enabled=bool(d.get("enable", True)),
        weight=int(d.get("weight") or 0),
        order=int(d.get("serialNumber") or 0),
        remark=_s(d.get("sourceRemark")),
        headers=headers,
        search_url=_s(d.get("ruleSearchUrl")),
        explore_url=_s(d.get("ruleFindUrl")),
        book_url_pattern=_s(d.get("ruleBookUrlPattern")),
        search=search,
        # 旧格式的发现页沿用搜索列表规则
        explore=search,
        info=InfoRule(
            name=_s(d.get("ruleBookName")),
            author=_s(d.get("ruleBookAuthor")),
            kind=_s(d.get("ruleBookKind")),
            intro=_s(d.get("ruleIntroduce")),
            last_chapter=_s(d.get("ruleBookLastChapter")),
            cover_url=_s(d.get("ruleCoverUrl")),
            toc_url=_s(d.get("ruleChapterUrl")),
        ),
        toc=TocRule(
            chapter_list=_s(d.get("ruleChapterList")),
            chapter_name=_s(d.get("ruleChapterName")),
            chapter_url=_s(d.get("ruleContentUrl")),
            next_toc_url=_s(d.get("ruleChapterUrlNext")),
        ),
        content=ContentRule(
            content=_s(d.get("ruleBookContent")),
            next_content_url=_s(d.get("ruleContentUrlNext")),
        ),
    )


def _list_rule(o: dict) -> ListRule:
    return ListRule(
        book_list=_s(o.get("bookList")),
        name=_s(o.get("name")),
        author=_s(o.get("author")),
        kind=_s(o.get("kind")),
        intro=_s(o.get("intro")),
        last_chapter=_s(o.get("lastChapter")),
        update_time=_s(o.get("updateTime")),
        cover_url=_s(o.get("coverUrl")),
        book_url=_s(o.get("bookUrl")),
        word_count=_s(o.get("wordCount")),
    )


def _parse_legado(d: dict, url: str, name: str) -> SourceRules:
    search = _list_rule(_obj(d.get("ruleSearch")))
    explore = _list_rule(_obj(d.get("ruleExplore")))
    # 发现规则缺字段时回落到搜索规则
    for f in explore.__dataclass_fields__:
        if not getattr(explore, f):
            setattr(explore, f, getattr(search, f))
    bi = _obj(d.get("ruleBookInfo"))
    toc = _obj(d.get("ruleToc"))
    ct = _obj(d.get("ruleContent"))
    return SourceRules(
        source_url=url,
        name=name,
        group=_s(d.get("bookSourceGroup")),
        type=_source_type(d.get("bookSourceType")),
        format="legado",
        enabled=bool(d.get("enabled", True)),
        weight=int(d.get("weight") or 0),
        order=int(d.get("customOrder") or 0),
        remark=_s(d.get("bookSourceComment")),
        headers=_parse_headers(d.get("header")),
        js_lib=_s(d.get("jsLib")),
        search_url=_s(d.get("searchUrl")),
        explore_url=_s(d.get("exploreUrl")),
        book_url_pattern=_s(d.get("bookUrlPattern")),
        search=search,
        explore=explore,
        info=InfoRule(
            init=_s(bi.get("init")),
            name=_s(bi.get("name")),
            author=_s(bi.get("author")),
            kind=_s(bi.get("kind")),
            intro=_s(bi.get("intro")),
            last_chapter=_s(bi.get("lastChapter")),
            update_time=_s(bi.get("updateTime")),
            cover_url=_s(bi.get("coverUrl")),
            toc_url=_s(bi.get("tocUrl")),
            word_count=_s(bi.get("wordCount")),
        ),
        toc=TocRule(
            chapter_list=_s(toc.get("chapterList")),
            chapter_name=_s(toc.get("chapterName")),
            chapter_url=_s(toc.get("chapterUrl")),
            next_toc_url=_s(toc.get("nextTocUrl")),
            update_time=_s(toc.get("updateTime")),
            is_volume=_s(toc.get("isVolume")),
        ),
        content=ContentRule(
            content=_s(ct.get("content")),
            next_content_url=_s(ct.get("nextContentUrl")),
            title=_s(ct.get("title")),
            image_style=_s(ct.get("imageStyle")),
            replace_regex=_s(ct.get("replaceRegex")),
        ),
    )


def default_headers(src: SourceRules) -> dict[str, str]:
    h = {"User-Agent": DEFAULT_UA}
    h.update(src.headers)
    return h


def image_headers(src: SourceRules) -> dict[str, str]:
    """图片请求默认带上源的 UA，Referer 指向源站（大多数漫画 CDN 防盗链需要）。"""
    h = default_headers(src)
    h.setdefault("Referer", src.base_url + "/")
    return h
