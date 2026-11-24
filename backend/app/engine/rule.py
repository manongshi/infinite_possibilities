"""规则求值器（参考 Legado 的 AnalyzeRule 语义，按需实现常用子集）。

支持：
* JSoup 默认语法：`class.xxx.0@tag.li@text`、`id.x`、`tag.a.-1`、`children`、`!0` 排除、`[0:3]` 区间
* CSS：任何不以 class./tag./id./text./children 开头的段都按 CSS 选择器处理；`@css:` 前缀强制整段 CSS
* XPath：`@xpath:` 前缀或以 `/` 开头
* JSONPath：`@json:` 前缀或以 `$.`、`$[` 开头；内容本身是 JSON 时默认按 JSONPath
* JS：`@js:` 尾段、`<js>…</js>` 段、`{{ }}` 模板
* 组合：`&&` 合并、`||` 取第一个非空、`%%` 交错；`##正则##替换` / `###` 只替换第一个
* 列表规则前缀 `-` 倒序，`+` 正序
* 规则尾部 `@Header:{...}` 由调用方用 split_header 拆出
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import lxml.html
from jsonpath_ng.ext import parse as jsonpath_parse
from lxml import etree

from .js import eval_js

_JSOUP_HEADS = ("class", "tag", "id", "text", "children")
_INDEX_DOT = re.compile(r"^(.*?)([.!])(-?\d+(?::-?\d*)*(?:,-?\d+)*)$")
_INDEX_BRACKET = re.compile(r"^(.*?)\[(!?-?\d*(?::-?\d*)*(?:,-?\d+(?::-?\d*)*)*)\]$")
_HEADER_SPLIT = re.compile(r"@Header:\s*(\{.*\})\s*$", re.S)


class RuleError(RuntimeError):
    pass


# --------------------------------------------------------------------------- helpers


def split_header(rule: str) -> tuple[str, dict[str, str]]:
    """拆出规则尾部的 `@Header:{...}`。"""
    if not rule or "@Header:" not in rule:
        return rule, {}
    m = _HEADER_SPLIT.search(rule)
    if not m:
        return rule, {}
    try:
        h = json.loads(m.group(1))
    except json.JSONDecodeError:
        return rule, {}
    return rule[: m.start()], {str(k): str(v) for k, v in h.items()}


def _is_element(x: Any) -> bool:
    return isinstance(x, etree._Element)


def _outer_html(el: Any) -> str:
    return lxml.html.tostring(el, encoding="unicode", with_tail=False)


def _norm_text(s: str) -> str:
    return " ".join(s.split())


_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "dl", "dt", "dd", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header", "footer",
}


def _element_text(el: Any) -> str:
    """类似 jsoup 的 text()：行内元素直接拼接，块级元素之间补空格，合并空白，跳过 script/style。"""
    chunks: list[str] = []

    def walk(node: Any) -> None:
        if not isinstance(node.tag, str) or node.tag in ("script", "style"):
            return
        block = node.tag in _BLOCK_TAGS
        if block:
            chunks.append(" ")
        if node.text:
            chunks.append(node.text)
        for c in node:
            walk(c)
            if c.tail:
                chunks.append(c.tail)
        if block:
            chunks.append(" ")

    walk(el)
    return _norm_text("".join(chunks))


def _own_text_nodes(el: Any) -> list[str]:
    out = []
    if el.text and el.text.strip():
        out.append(el.text.strip())
    for c in el:
        if c.tail and c.tail.strip():
            out.append(c.tail.strip())
    return out


def _parse_html(s: str) -> Any:
    s = s.strip()
    if not s:
        return lxml.html.fragment_fromstring("<div></div>")
    if re.search(r"<html|<body|<!doctype", s[:2000], re.I):
        return lxml.html.document_fromstring(s)
    return lxml.html.fragment_fromstring(s, create_parent="div")


def _try_json(s: str) -> Any:
    t = s.strip()
    if t[:1] in ("{", "["):
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            return None
    return None


def _split_top(s: str, sep: str) -> list[str]:
    """按分隔符切开，忽略括号 / 引号内部的分隔符。"""
    out, depth, quote, buf, i = [], 0, "", [], 0
    while i < len(s):
        ch = s[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            out.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def _apply_index(nodes: list, spec: str, exclude: bool) -> list:
    n = len(nodes)
    if n == 0 or spec == "":
        return nodes
    picked: list[int] = []
    for part in spec.split(","):
        if ":" in part:
            seg = part.split(":")
            start = int(seg[0]) if seg[0] not in ("", "-") else 0
            end = int(seg[1]) if len(seg) > 1 and seg[1] not in ("", "-") else n - 1
            step = int(seg[2]) if len(seg) > 2 and seg[2] else 1
            start = start + n if start < 0 else start
            end = end + n if end < 0 else end
            if step == 0:
                step = 1
            rng = range(start, end + 1, step) if start <= end else range(start, end - 1, -abs(step))
            picked.extend(i for i in rng if 0 <= i < n)
        else:
            i = int(part)
            i = i + n if i < 0 else i
            if 0 <= i < n:
                picked.append(i)
    if exclude:
        drop = set(picked)
        return [x for i, x in enumerate(nodes) if i not in drop]
    return [nodes[i] for i in picked]


def _split_index(part: str) -> tuple[str, str, bool]:
    m = _INDEX_BRACKET.match(part)
    if m and m.group(1):
        spec = m.group(2)
        excl = spec.startswith("!")
        return m.group(1), spec.lstrip("!"), excl
    m = _INDEX_DOT.match(part)
    if m and m.group(1):
        return m.group(1), m.group(3), m.group(2) == "!"
    return part, "", False


def _css(el: Any, sel: str) -> list:
    sel = sel.strip()
    if not sel:
        return [el]
    try:
        return el.cssselect(sel)
    except Exception as e:  # noqa: BLE001
        raise RuleError(f"CSS 选择器错误: {sel} ({e})") from e


def _select_part(el: Any, part: str) -> list:
    sel, idx, excl = _split_index(part.strip())
    head, dot, rest = sel.partition(".")
    if head in _JSOUP_HEADS and (dot or head == "children"):
        if head == "class":
            classes = rest.split()
            cond = " and ".join(
                f"contains(concat(' ', normalize-space(@class), ' '), ' {c} ')" for c in classes
            )
            nodes = el.xpath(f".//*[{cond}]") if cond else []
        elif head == "tag":
            nodes = [n for n in el.iter(rest) if n is not el]
        elif head == "id":
            nodes = el.xpath(".//*[@id=$v]", v=rest)
        elif head == "text":
            nodes = el.xpath(".//*[text()[contains(., $v)]]", v=rest)
        else:
            nodes = [c for c in el if isinstance(c.tag, str)]
    else:
        nodes = _css(el, sel)
    return _apply_index(nodes, idx, excl) if idx else nodes


def _get_attr(el: Any, name: str) -> list[str]:
    name = name.strip()
    if name == "text":
        return [_element_text(el)]
    if name == "textNodes":
        return ["\n".join(_own_text_nodes(el))]
    if name == "ownText":
        return ["".join(_own_text_nodes(el))]
    if name in ("html", "all"):
        return [_outer_html(el)]
    v = el.get(name)
    return [v] if v is not None else []


# --------------------------------------------------------------------------- analyzer


class Analyzer:
    """对一份内容（HTML / JSON / 文本 / 已选中的元素）执行规则。"""

    def __init__(self, content: Any, base_url: str = "", variables: dict | None = None, js_lib: str = ""):
        self.raw = content
        self.base_url = base_url
        self.variables = variables or {}
        self.js_lib = js_lib
        self._html = None
        self._json = None

    # -- content views

    def _as_html(self, content: Any) -> Any:
        if _is_element(content):
            return content
        if content is self.raw and self._html is not None:
            return self._html
        node = _parse_html(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
        if content is self.raw:
            self._html = node
        return node

    def _as_json(self, content: Any) -> Any:
        if isinstance(content, (dict, list)):
            return content
        if isinstance(content, str):
            if content is self.raw and self._json is not None:
                return self._json
            j = _try_json(content)
            if content is self.raw:
                self._json = j
            return j
        return None

    def _js(self, code: str, result: Any) -> Any:
        def conv(x: Any) -> Any:
            if _is_element(x):
                return _outer_html(x)
            if isinstance(x, list):
                return [conv(i) for i in x]
            return x

        src = self.raw if isinstance(self.raw, str) else conv(self.raw)
        vars_ = {"result": conv(result), "baseUrl": self.base_url, "src": src}
        vars_.update(self.variables)
        return eval_js(code, vars_, self.js_lib)

    # -- step splitting

    @staticmethod
    def _steps(rule: str) -> list[tuple[str, str]]:
        steps: list[tuple[str, str]] = []
        rest = rule
        while rest:
            low = rest.lower()
            js_tag = low.find("<js>")
            at_js = low.find("@js:")
            if js_tag == -1 and at_js == -1:
                steps.append(("rule", rest))
                break
            if at_js != -1 and (js_tag == -1 or at_js < js_tag):
                if rest[:at_js].strip():
                    steps.append(("rule", rest[:at_js]))
                steps.append(("js", rest[at_js + 4 :]))
                break
            if rest[:js_tag].strip():
                steps.append(("rule", rest[:js_tag]))
            end = low.find("</js>", js_tag)
            if end == -1:
                steps.append(("js", rest[js_tag + 4 :]))
                break
            steps.append(("js", rest[js_tag + 4 : end]))
            rest = rest[end + 5 :]
        return [(k, v) for k, v in steps if k == "js" or v.strip()]

    # -- core evaluation

    def _eval_single(self, content: Any, rule: str, want: str) -> list:
        """want: 'elements' 返回节点列表；'strings' 返回字符串列表。"""
        rule = rule.strip()
        if not rule:
            return [content] if want == "elements" else []

        replace = None
        if "##" in rule:
            parts = rule.split("##")
            rule = parts[0]
            regex = parts[1] if len(parts) > 1 else ""
            repl = parts[2] if len(parts) > 2 else ""
            first_only = len(parts) > 3
            replace = (regex, repl, first_only)
            if not rule.strip():
                # 纯替换规则，作用在当前内容文本上
                vals = [content if isinstance(content, str) else self._text_of(content)]
                return [self._do_replace(v, replace) for v in vals]

        low = rule.lower()
        if low.startswith("@css:"):
            vals = self._eval_jsoup(content, rule[5:], want, css_only=True)
        elif low.startswith("@json:") or rule.startswith("$.") or rule.startswith("$["):
            vals = self._eval_json(content, rule[6:] if low.startswith("@json:") else rule, want)
        elif low.startswith("@xpath:") or rule.startswith("/"):
            vals = self._eval_xpath(content, rule[7:] if low.startswith("@xpath:") else rule, want)
        elif isinstance(content, (dict, list)) or (
            isinstance(content, str) and not _is_element(content) and _try_json(content) is not None
            and not rule.startswith(("class.", "tag.", "id.", "text.", "children"))
        ):
            vals = self._eval_json(content, rule if rule.startswith("$") else "$." + rule, want)
        else:
            vals = self._eval_jsoup(content, rule, want)

        if replace and want == "strings":
            vals = [self._do_replace(v, replace) for v in vals]
        return vals

    @staticmethod
    def _do_replace(v: str, rep: tuple[str, str, bool]) -> str:
        regex, repl, first_only = rep
        if not regex:
            return v
        repl_py = re.sub(r"\$(\d)", r"\\\1", repl)
        try:
            if first_only:
                m = re.search(regex, v)
                return m.expand(repl_py) if m else ""
            return re.sub(regex, repl_py, v)
        except re.error:
            return v

    def _text_of(self, x: Any) -> str:
        if _is_element(x):
            return _element_text(x)
        if isinstance(x, (dict, list)):
            return json.dumps(x, ensure_ascii=False)
        return "" if x is None else str(x)

    def _eval_jsoup(self, content: Any, rule: str, want: str, css_only: bool = False) -> list:
        root = self._as_html(content)
        if css_only:
            sel, _, attr = rule.rpartition("@") if want == "strings" else (rule, "", "")
            if want == "strings" and not sel:
                sel, attr = attr, "text"
            nodes = _css(root, sel)
            if want == "elements":
                return nodes
            out: list[str] = []
            for n in nodes:
                out.extend(_get_attr(n, attr))
            return out

        parts = [p for p in _split_top(rule, "@") if p.strip() != ""]
        if want == "strings":
            *sel_parts, attr = parts if parts else ["text"]
        else:
            sel_parts, attr = parts, ""
        nodes = [root]
        for p in sel_parts:
            nxt: list = []
            for n in nodes:
                nxt.extend(_select_part(n, p))
            nodes = nxt
        if want == "elements":
            return nodes
        out = []
        for n in nodes:
            out.extend(_get_attr(n, attr))
        return out

    def _eval_xpath(self, content: Any, rule: str, want: str) -> list:
        root = self._as_html(content)
        try:
            res = root.xpath(rule)
        except etree.XPathError as e:
            raise RuleError(f"XPath 错误: {rule} ({e})") from e
        if not isinstance(res, list):
            res = [res]
        if want == "elements":
            return res
        return [_element_text(r) if _is_element(r) else str(r) for r in res]

    def _eval_json(self, content: Any, rule: str, want: str) -> list:
        data = self._as_json(content)
        if data is None:
            return []
        try:
            matches = [m.value for m in jsonpath_parse(rule).find(data)]
        except Exception as e:  # noqa: BLE001
            raise RuleError(f"JSONPath 错误: {rule} ({e})") from e
        if want == "elements":
            if len(matches) == 1 and isinstance(matches[0], list):
                return matches[0]
            return matches
        out = []
        for v in matches:
            if isinstance(v, list):
                out.extend(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in v)
            elif isinstance(v, str):
                out.append(v)
            elif v is None:
                continue
            else:
                out.append(json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v))
        return out

    def _eval_combined(self, content: Any, rule: str, want: str) -> list:
        for sep, mode in (("||", "or"), ("&&", "and"), ("%%", "zip")):
            parts = _split_top(rule, sep)
            if len(parts) > 1:
                results = []
                for p in parts:
                    r = self._eval_single(content, p, want)
                    if mode == "or" and any(_is_element(x) or str(x).strip() for x in r):
                        return r
                    results.append(r)
                if mode == "or":
                    return []
                if mode == "and":
                    return [x for r in results for x in r]
                out = []
                for i in range(max(len(r) for r in results)):
                    for r in results:
                        if i < len(r):
                            out.append(r[i])
                return out
        return self._eval_single(content, rule, want)

    def _run(self, content: Any, rule: str, want: str) -> Any:
        """执行一条完整规则（可能包含多个 JS / 普通规则步骤）。返回 list 或 JS 的原始结果。"""
        cur: Any = content
        steps = self._steps(rule)
        for i, (kind, text) in enumerate(steps):
            if kind == "js":
                cur = self._js(text, cur)
            else:
                is_last = i == len(steps) - 1
                step_want = want if is_last else ("strings" if want == "strings" and self._next_is_js(steps, i) else "elements")
                if isinstance(cur, list) and not is_last and step_want == "elements":
                    res = []
                    for c in cur:
                        res.extend(self._eval_combined(c, text, "elements"))
                    cur = res
                elif isinstance(cur, list):
                    res = []
                    for c in cur:
                        res.extend(self._eval_combined(c, text, step_want))
                    cur = res
                else:
                    cur = self._eval_combined(cur, text, step_want)
        return cur

    @staticmethod
    def _next_is_js(steps: list, i: int) -> bool:
        return i + 1 < len(steps) and steps[i + 1][0] == "js"

    def _render_templates(self, content: Any, rule: str) -> str:
        def rep(m: re.Match) -> str:
            expr = m.group(1)
            e = expr.strip()
            if e.startswith(("@", "$.", "$[", "//")):
                return self.get_string(e, content=content)
            v = self._js(e, content)
            return "" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))

        return re.sub(r"\{\{([\s\S]*?)\}\}", rep, rule)

    # -- public API

    def get_elements(self, rule: str, content: Any = None) -> list:
        content = self.raw if content is None else content
        rule = (rule or "").strip()
        if not rule:
            return []
        reverse = False
        if rule.startswith("-"):
            reverse, rule = True, rule[1:]
        elif rule.startswith("+"):
            rule = rule[1:]
        res = self._run(content, rule, "elements")
        if isinstance(res, str):
            j = _try_json(res)
            res = j if isinstance(j, list) else ([j] if j is not None else [res])
        elif res is None:
            res = []
        elif not isinstance(res, list):
            res = [res]
        if reverse:
            res = list(reversed(res))
        return res

    def get_strings(self, rule: str, content: Any = None, is_url: bool = False) -> list[str]:
        content = self.raw if content is None else content
        rule = (rule or "").strip()
        if not rule:
            return []
        if "{{" in rule and not rule.lower().startswith(("@js:", "<js>")):
            vals = [self._render_templates(content, rule)]
        else:
            res = self._run(content, rule, "strings")
            if res is None:
                vals = []
            elif isinstance(res, list):
                vals = [self._text_of(x) if not isinstance(x, str) else x for x in res]
            else:
                vals = [self._text_of(res) if not isinstance(res, str) else res]
        vals = [v.strip() for v in vals if v is not None and str(v).strip()]
        if is_url:
            vals = [self.abs_url(v) for v in vals]
        return vals

    def get_string(self, rule: str, content: Any = None, is_url: bool = False) -> str:
        vals = self.get_strings(rule, content=content, is_url=False)
        if not vals:
            return ""
        if is_url:
            return self.abs_url(vals[0])
        return "\n".join(vals)

    def get_value(self, rule: str, content: Any = None) -> Any:
        """返回原始结果（JS 可能返回数组/对象），正文规则用。"""
        content = self.raw if content is None else content
        rule = (rule or "").strip()
        if not rule:
            return content
        res = self._run(content, rule, "strings")
        if isinstance(res, list):
            return [x if isinstance(x, (str, dict, list)) else self._text_of(x) for x in res]
        return res

    def abs_url(self, u: str) -> str:
        u = (u or "").strip()
        if not u or u.startswith(("data:", "javascript:")):
            return u
        # Legado 允许 url 后面跟 ,{json 选项}，拼接时保留
        opt = ""
        m = re.search(r",\s*\{[\s\S]*\}$", u)
        if m and not u.startswith("{"):
            u, opt = u[: m.start()], u[m.start():]
        return urljoin(self.base_url, u) + opt if self.base_url else u + opt
