"""书源 JS 运行时（V8，基于 mini-racer）。

规则里的 `@js:` / `<js></js>` / `{{ }}` 都走这里。每次求值新建一个隔离上下文，
注入 result / baseUrl / key / page / book / chapter / source 等变量，以及一个最小化的 `java` 对象。

暂未实现需要回调 Python 的能力（java.ajax、java.put/get 持久化等），留待以后扩展。
"""
from __future__ import annotations

import json
from typing import Any

from py_mini_racer import MiniRacer

_PRELUDE = r"""
var __vars = {};
var java = {
  log: function (s) { return s; },
  put: function (k, v) { __vars[k] = v; return v; },
  get: function (k) { return __vars[k] === undefined ? "" : __vars[k]; },
  encodeURI: function (s) { return encodeURIComponent(s); },
  base64Decode: function (s) {
    var K = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    s = String(s).replace(/[^A-Za-z0-9+/]/g, "");
    var out = [], buf = 0, bits = 0;
    for (var i = 0; i < s.length; i++) {
      buf = (buf << 6) | K.indexOf(s.charAt(i)); bits += 6;
      if (bits >= 8) { bits -= 8; out.push((buf >> bits) & 255); }
    }
    try { return decodeURIComponent(out.map(function (b) { return "%" + ("0" + b.toString(16)).slice(-2); }).join("")); }
    catch (e) { return String.fromCharCode.apply(null, out); }
  },
  timeFormat: function (t) { return new Date(Number(t)).toISOString(); }
};
var cookie = { getCookie: function () { return ""; } };
var source = {};
"""


class JsError(RuntimeError):
    pass


def eval_js(code: str, variables: dict[str, Any] | None = None, js_lib: str = "") -> Any:
    """执行一段 JS，返回最后一个表达式的值（JSON 可序列化的部分转成 Python 对象）。"""
    ctx = MiniRacer()
    try:
        ctx.eval(_PRELUDE)
        if js_lib:
            ctx.eval(js_lib)
        for k, v in (variables or {}).items():
            ctx.eval(f"var {k} = {json.dumps(v, ensure_ascii=False, default=str)};")
        ctx.eval(f"var __src = {json.dumps(code, ensure_ascii=False)};")
        # 间接 eval：在全局作用域执行，返回完成值；再 JSON 化带回 Python
        raw = ctx.eval(
            "(function(){ var r = (0, eval)(__src);"
            " if (r === undefined || r === null) return null;"
            " if (typeof r === 'object') { try { return JSON.stringify({v: r}); } catch (e) { return JSON.stringify({v: String(r)}); } }"
            " return JSON.stringify({v: r}); })()",
            timeout=10_000,
        )
    except Exception as e:  # noqa: BLE001
        raise JsError(f"JS 执行失败: {e}") from e
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
    if raw is None:
        return None
    return json.loads(raw)["v"]
