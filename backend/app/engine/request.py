"""URL 规则编译 + HTTP 请求。

支持：
* 旧格式：`searchKey` / `searchPage` / `searchPage-1` 占位，`|char=gbk` 编码，`url@k=v&k2=v2` 表示 POST
* Legado：`{{key}}` / `{{page}}` / `{{js 表达式}}`、`<,{{page}}>` 分页列表、`url,{"method":"POST","body":…,"charset":…,"headers":{…}}`
* `@js:` / `<js>` 开头的 URL 规则（JS 返回最终 URL）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin

import httpx

from ..config import HTTP_TIMEOUT
from .js import eval_js
from .source import SourceRules, default_headers


class FetchError(RuntimeError):
    pass


@dataclass
class Req:
    url: str
    method: str = "GET"
    body: str | None = None
    charset: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Resp:
    url: str
    status: int
    text: str
    headers: dict[str, str]


def _page_list(rule: str, page: int) -> str:
    """Legado `<a,b,c>`：第 page 页取第 page 个，超出取最后一个。"""

    def rep(m: re.Match) -> str:
        items = m.group(1).split(",")
        return items[min(page, len(items)) - 1]

    return re.sub(r"<([^<>]*,[^<>]*)>", rep, rule)


def build_request(
    src: SourceRules,
    url_rule: str,
    *,
    key: str | None = None,
    page: int = 1,
    base_url: str | None = None,
    extra_vars: dict | None = None,
) -> Req:
    rule = (url_rule or "").strip()
    if not rule:
        raise FetchError("URL 规则为空")
    base = base_url or src.base_url + "/"
    js_vars = {"key": key or "", "page": page, "baseUrl": base, **(extra_vars or {})}

    low = rule.lower()
    if low.startswith("@js:"):
        rule = str(eval_js(rule[4:], js_vars, src.js_lib) or "")
    elif low.startswith("<js>"):
        end = low.rfind("</js>")
        rule = str(eval_js(rule[4:end if end != -1 else None], js_vars, src.js_lib) or "")

    charset = ""
    m = re.search(r"\|char=([\w-]+)", rule)
    if m:
        charset = m.group(1)
        rule = rule[: m.start()] + rule[m.end():]

    # Legado: url,{json}
    options: dict = {}
    om = re.search(r",\s*(\{[\s\S]*\})\s*$", rule)
    if om:
        try:
            options = json.loads(om.group(1))
            rule = rule[: om.start()]
        except json.JSONDecodeError:
            options = {}
    charset = str(options.get("charset") or charset)

    enc_key = quote(key or "", safe="", encoding=charset or "utf-8") if key is not None else ""

    rule = _page_list(rule, page)

    def tpl(mm: re.Match) -> str:
        expr = mm.group(1).strip()
        if expr == "key":
            return key or ""
        if expr == "page":
            return str(page)
        v = eval_js(expr, js_vars, src.js_lib)
        return "" if v is None else str(v)

    rule = re.sub(r"\{\{([\s\S]*?)\}\}", tpl, rule)

    if src.format == "legacy":
        rule = rule.replace("searchKey", enc_key)
        rule = re.sub(
            r"searchPage([+-]\d+)?",
            lambda mm: str(page + int(mm.group(1) or 0)),
            rule,
        )

    method = str(options.get("method") or "GET").upper()
    body = options.get("body")
    if body is not None and not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False)

    # 旧格式 POST：url@k=v&k2=v2（@ 出现在路径之后）
    if src.format == "legacy" and "@" in rule:
        head, _, tail = rule.rpartition("@")
        if "=" in tail and "/" not in tail:
            rule, body, method = head, tail, "POST"

    headers = default_headers(src)
    if isinstance(options.get("headers"), dict):
        headers.update({str(k): str(v) for k, v in options["headers"].items()})
    elif isinstance(options.get("headers"), str):
        try:
            headers.update(json.loads(options["headers"]))
        except json.JSONDecodeError:
            pass

    url = urljoin(base, rule.strip())
    return Req(url=url, method=method, body=body, charset=charset, headers=headers)


def parse_url_with_options(src: SourceRules, url: str) -> Req:
    """详情/目录/正文 URL 可能带 `,{json}` 选项，复用同一套解析（不做 key/page 替换）。"""
    return build_request(src, url, key=None, page=1)


_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=HTTP_TIMEOUT,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=16),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _decode(resp: httpx.Response, charset: str) -> str:
    if charset:
        return resp.content.decode(charset, errors="replace")
    ct = resp.headers.get("content-type", "")
    if "charset=" in ct.lower():
        return resp.text
    head = resp.content[:4096].decode("ascii", errors="ignore")
    m = re.search(r"<meta[^>]+charset=[\"']?([\w-]+)", head, re.I)
    if m:
        try:
            return resp.content.decode(m.group(1), errors="replace")
        except LookupError:
            pass
    return resp.content.decode("utf-8", errors="replace")


async def fetch(req: Req) -> Resp:
    data = None
    headers = dict(req.headers)
    if req.body is not None:
        data = req.body.encode(req.charset or "utf-8")
        if req.body.lstrip().startswith(("{", "[")):
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        else:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    try:
        r = await client().request(req.method, req.url, headers=headers, content=data)
    except httpx.HTTPError as e:
        raise FetchError(f"请求失败 {req.url}: {e!r}") from e
    if r.status_code >= 400:
        raise FetchError(f"请求失败 {req.url}: HTTP {r.status_code}")
    return Resp(url=str(r.url), status=r.status_code, text=_decode(r, req.charset), headers=dict(r.headers))
