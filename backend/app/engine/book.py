"""书源解析流水线：搜索 / 发现 / 详情 / 目录 / 正文。

所有规则求值都是 CPU 密集（lxml、V8），放到线程池里跑，避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .request import FetchError, Req, build_request, fetch
from .rule import Analyzer, split_header
from .source import ListRule, SourceRules, default_headers, image_headers

MAX_TOC_PAGES = 50
MAX_CONTENT_PAGES = 30


@dataclass
class BookItem:
    name: str
    book_url: str
    author: str = ""
    cover_url: str = ""
    kind: str = ""
    intro: str = ""
    last_chapter: str = ""
    update_time: str = ""
    word_count: str = ""


@dataclass
class BookInfo:
    name: str
    book_url: str
    toc_url: str
    author: str = ""
    cover_url: str = ""
    kind: str = ""
    intro: str = ""
    last_chapter: str = ""
    update_time: str = ""
    word_count: str = ""


@dataclass
class Chapter:
    index: int
    title: str
    url: str
    is_volume: bool = False


@dataclass
class ImageRef:
    url: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Content:
    url: str
    images: list[ImageRef]
    text: str = ""
    next_url: str = ""


@dataclass
class ExploreKind:
    title: str
    url: str
    group: str = ""


def to_dict(x: Any) -> Any:
    if isinstance(x, list):
        return [to_dict(i) for i in x]
    return asdict(x)


async def _run(fn, *args):
    return await asyncio.to_thread(fn, *args)


# ----------------------------------------------------------------- list (search / explore)


def _parse_book_list(src: SourceRules, rule: ListRule, html: str, url: str, vars_: dict) -> list[BookItem]:
    a = Analyzer(html, base_url=url, variables=vars_, js_lib=src.js_lib)
    items = a.get_elements(rule.book_list)
    books: list[BookItem] = []
    seen: set[str] = set()
    for el in items:
        name = a.get_string(rule.name, content=el)
        book_url = a.get_string(rule.book_url, content=el, is_url=True) if rule.book_url else url
        if not name or not book_url or book_url in seen:
            continue
        seen.add(book_url)
        books.append(
            BookItem(
                name=name,
                book_url=book_url,
                author=a.get_string(rule.author, content=el),
                cover_url=a.get_string(rule.cover_url, content=el, is_url=True),
                kind=",".join(a.get_strings(rule.kind, content=el)),
                intro=a.get_string(rule.intro, content=el),
                last_chapter=a.get_string(rule.last_chapter, content=el),
                update_time=a.get_string(rule.update_time, content=el),
                word_count=a.get_string(rule.word_count, content=el),
            )
        )
    return books


def _match_book_pattern(src: SourceRules, url: str) -> bool:
    p = src.book_url_pattern.strip()
    if not p or p == "NONE":
        return False
    try:
        return re.search(p, url) is not None
    except re.error:
        return False


async def search(src: SourceRules, key: str, page: int = 1) -> list[BookItem]:
    if not src.search_url:
        return []
    req = build_request(src, src.search_url, key=key, page=page)
    if page > 1 and not _has_page_placeholder(src.search_url, src.format):
        return []
    resp = await fetch(req)
    # 搜索结果直接跳到了详情页
    if _match_book_pattern(src, resp.url):
        info = await _run(_parse_info, src, resp.text, resp.url)
        return [BookItem(name=info.name, book_url=resp.url, author=info.author, cover_url=info.cover_url,
                         kind=info.kind, intro=info.intro, last_chapter=info.last_chapter)]
    return await _run(_parse_book_list, src, src.search, resp.text, resp.url, {"key": key, "page": page})


def _has_page_placeholder(url_rule: str, fmt: str) -> bool:
    if "{{page" in url_rule or "page}}" in url_rule or re.search(r"<[^<>]*,[^<>]*>", url_rule):
        return True
    if fmt == "legacy" and "searchPage" in url_rule:
        return True
    return url_rule.lstrip().lower().startswith(("@js:", "<js>")) and "page" in url_rule


def explore_kinds(src: SourceRules) -> list[ExploreKind]:
    raw = (src.explore_url or "").strip()
    if not raw:
        return []
    kinds: list[ExploreKind] = []
    if raw.lower().startswith(("@js:", "<js>")):
        from .js import eval_js

        code = raw[4:] if raw.lower().startswith("@js:") else raw[4:].rsplit("</js>", 1)[0]
        try:
            v = eval_js(code, {"baseUrl": src.base_url}, src.js_lib)
        except Exception:  # noqa: BLE001
            return []
        raw = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            group = ""
            for o in arr:
                title, url = str(o.get("title", "")), str(o.get("url", "") or "")
                if not url:
                    group = title  # 没 url 的项当作分组标题
                    continue
                kinds.append(ExploreKind(title=title, url=url, group=group))
            return kinds
        except (json.JSONDecodeError, AttributeError):
            pass
    group = ""
    for line in re.split(r"\n|&&", raw):
        line = line.strip()
        if not line:
            continue
        if "::" not in line:
            group = line
            continue
        title, url = line.split("::", 1)
        if url.strip():
            kinds.append(ExploreKind(title=title.strip(), url=url.strip(), group=group))
        else:
            group = title.strip()
    return kinds


async def explore(src: SourceRules, url_rule: str, page: int = 1) -> tuple[list[BookItem], bool]:
    """返回 (书列表, 是否可能还有下一页)。"""
    has_page = _has_page_placeholder(url_rule, src.format)
    if page > 1 and not has_page:
        return [], False
    req = build_request(src, url_rule, page=page)
    resp = await fetch(req)
    books = await _run(_parse_book_list, src, src.explore, resp.text, resp.url, {"page": page})
    return books, has_page and len(books) > 0


# ----------------------------------------------------------------- detail


def _parse_info(src: SourceRules, html: str, url: str) -> BookInfo:
    r = src.info
    a = Analyzer(html, base_url=url, js_lib=src.js_lib)
    content: Any = html
    if r.init.strip():
        els = a.get_elements(r.init)
        content = els[0] if els else html
    toc_url = a.get_string(r.toc_url, content=content, is_url=True) if r.toc_url else ""
    return BookInfo(
        name=a.get_string(r.name, content=content),
        book_url=url,
        toc_url=toc_url or url,
        author=a.get_string(r.author, content=content),
        cover_url=a.get_string(r.cover_url, content=content, is_url=True),
        kind=",".join(a.get_strings(r.kind, content=content)),
        intro=a.get_string(r.intro, content=content),
        last_chapter=a.get_string(r.last_chapter, content=content),
        update_time=a.get_string(r.update_time, content=content),
        word_count=a.get_string(r.word_count, content=content),
    )


async def book_info(src: SourceRules, book_url: str) -> BookInfo:
    resp = await fetch(_req_for(src, book_url))
    info = await _run(_parse_info, src, resp.text, resp.url)
    info.book_url = book_url
    return info


def _req_for(src: SourceRules, url: str) -> Req:
    return build_request(src, url) if ",{" in url else Req(url=url, headers=default_headers(src))


# ----------------------------------------------------------------- toc


def _parse_toc(src: SourceRules, html: str, url: str, start: int) -> tuple[list[Chapter], list[str]]:
    r = src.toc
    a = Analyzer(html, base_url=url, js_lib=src.js_lib)
    els = a.get_elements(r.chapter_list)
    chapters: list[Chapter] = []
    for el in els:
        title = a.get_string(r.chapter_name, content=el)
        ch_url = a.get_string(r.chapter_url, content=el, is_url=True) if r.chapter_url else ""
        is_vol = bool(r.is_volume) and a.get_string(r.is_volume, content=el).lower() in ("true", "1", "yes")
        if not title:
            continue
        chapters.append(Chapter(index=start + len(chapters), title=title, url=ch_url or url, is_volume=is_vol))
    nexts = a.get_strings(r.next_toc_url, is_url=True) if r.next_toc_url else []
    return chapters, nexts


async def chapter_list(src: SourceRules, toc_url: str) -> list[Chapter]:
    chapters: list[Chapter] = []
    visited: set[str] = set()
    queue = [toc_url]
    while queue and len(visited) < MAX_TOC_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        resp = await fetch(_req_for(src, url))
        chs, nexts = await _run(_parse_toc, src, resp.text, resp.url, len(chapters))
        chapters.extend(chs)
        queue.extend(n for n in nexts if n and n not in visited)
    # 去重（同一 url 只保留第一次）并重新编号
    seen: set[str] = set()
    out: list[Chapter] = []
    for c in chapters:
        if c.url in seen and not c.is_volume:
            continue
        seen.add(c.url)
        c.index = len(out)
        out.append(c)
    return out


# ----------------------------------------------------------------- content

_IMG_RE = re.compile(r"<img[^>]+?src\s*=\s*[\"']([^\"']+)[\"']", re.I)


def _image_ref(src: SourceRules, raw: str, base: str, rule_headers: dict[str, str], a: Analyzer) -> ImageRef | None:
    raw = raw.strip()
    if not raw:
        return None
    hdr = dict(image_headers(src))
    hdr.update(rule_headers)
    # Legado 漫画常见写法：url,{"headers":{...}}
    m = re.search(r",\s*(\{[\s\S]*\})\s*$", raw)
    if m:
        try:
            opt = json.loads(m.group(1))
            h = opt.get("headers")
            if isinstance(h, str):
                h = json.loads(h)
            if isinstance(h, dict):
                hdr.update({str(k): str(v) for k, v in h.items()})
            raw = raw[: m.start()]
        except json.JSONDecodeError:
            pass
    url = a.abs_url(raw)
    if not url.startswith(("http://", "https://")):
        return None
    return ImageRef(url=url, headers=hdr)


def _parse_content(src: SourceRules, html: str, url: str, extra: dict) -> Content:
    rule, rule_headers = split_header(src.content.content)
    a = Analyzer(html, base_url=url, variables=extra, js_lib=src.js_lib)
    value = a.get_value(rule) if rule.strip() else html

    raw_items: list[str] = []
    text = ""
    if isinstance(value, list):
        for v in value:
            if isinstance(v, str):
                found = _IMG_RE.findall(v)
                raw_items.extend(found if found else [v])
            elif isinstance(v, dict) and v.get("url"):
                raw_items.append(str(v["url"]))
    elif isinstance(value, str):
        j = None
        if value.strip().startswith("["):
            try:
                j = json.loads(value)
            except json.JSONDecodeError:
                j = None
        if isinstance(j, list):
            raw_items = [str(x) for x in j]
        else:
            found = _IMG_RE.findall(value)
            if found:
                raw_items = found
            else:
                lines = [ln.strip() for ln in value.splitlines() if ln.strip()]
                if lines and all(re.match(r"^(https?:)?//|^/", ln) for ln in lines):
                    raw_items = lines
                else:
                    text = value

    images = [img for img in (_image_ref(src, r, url, rule_headers, a) for r in raw_items) if img]
    next_url = ""
    if src.content.next_content_url:
        next_url = a.get_string(src.content.next_content_url, is_url=True)
    return Content(url=url, images=images, text=text, next_url=next_url)


async def content(src: SourceRules, chapter_url: str, next_chapter_url: str = "") -> Content:
    result = Content(url=chapter_url, images=[])
    url = chapter_url
    visited: set[str] = set()
    texts: list[str] = []
    while url and url not in visited and len(visited) < MAX_CONTENT_PAGES:
        visited.add(url)
        resp = await fetch(_req_for(src, url))
        part = await _run(_parse_content, src, resp.text, resp.url, {"nextChapterUrl": next_chapter_url})
        result.images.extend(part.images)
        if part.text:
            texts.append(part.text)
        nxt = part.next_url
        # 下一页指向下一章时停止
        if not nxt or (next_chapter_url and nxt.split("#")[0] == next_chapter_url.split("#")[0]):
            break
        url = nxt
    # 去重
    seen: set[str] = set()
    result.images = [i for i in result.images if not (i.url in seen or seen.add(i.url))]
    result.text = "\n".join(texts)
    return result


__all__ = [
    "BookItem", "BookInfo", "Chapter", "Content", "ExploreKind", "ImageRef", "FetchError",
    "search", "explore_kinds", "explore", "book_info", "chapter_list", "content", "to_dict",
]
