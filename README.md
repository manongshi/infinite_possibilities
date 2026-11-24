# Infinite

参考 [hadc188/reader](https://github.com/hadc188/reader)（Legado 生态）做的漫画阅读器。目前只做「看漫画」，结构上为以后加小说、书架、同步等留好了位置。

```
backend/   FastAPI + SQLite + 书源规则引擎
app/       Flutter（Android）
```

## 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8090
```

- 数据库：`backend/data/infinite.db`（SQLite，`INFINITE_DATABASE_URL` 可换成其他库）
- 首次启动库为空时，自动导入 `backend/seeds/*.json`（已放入「看漫画」源）
- 接口文档：http://localhost:8090/docs
- 测试：`.venv/bin/python -m pytest -q tests`
- 命令行跑一遍书源：`.venv/bin/python scripts/try_source.py seeds/manhuagui.json 海贼`

### 书源表 `book_sources`

一条记录 = 一个书源。`raw_json` 原样保存导入的 JSON，其余列（name / source_type / format / enabled / weight…）是为了筛选冗余出来的。按 `bookSourceUrl` 去重，重复导入会覆盖。

同时兼容两种格式（`app/engine/source.py` 统一成 `SourceRules`）：
- **legacy**：旧版「阅读」平铺字段（`ruleSearchUrl`、`ruleSearchList`、`ruleBookContent`…），也就是这次给的源
- **legado**：Legado 3 嵌套格式（`searchUrl`、`ruleSearch{}`、`ruleToc{}`、`ruleContent{}`…）

### 规则引擎（`app/engine/rule.py`）

CSS / JSoup 默认语法（`class.x.0@tag.li@text`）/ XPath / JSONPath / `@js:` `<js>` `{{}}`（V8，mini-racer）/ `&&` `||` `%%` / `##正则##替换` / `-` 倒序 / `@Header:`。

暂未实现：`java.ajax` 等需要回调后端的 JS API、登录、`@put/@get` 持久变量、WebView 渲染、图片解密。

### 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/sources?type=comic` | 书源列表 |
| POST | `/api/sources` | 导入（单个对象或数组） |
| POST | `/api/sources/import-url` | 从网络地址导入 |
| GET/PUT | `/api/sources/{id}/json` / `/api/sources/{id}` | 查看 / 修改原始 JSON |
| PATCH | `/api/sources/{id}/enabled` | 启停 |
| GET | `/api/sources/{id}/explore` | 发现分类 |
| GET | `/api/sources/{id}/explore/books?url=&page=` | 分类下的书 |
| GET | `/api/search?keyword=` | 并发搜索所有启用的漫画源 |
| GET | `/api/sources/{id}/book?url=` | 详情（含 `toc_url`） |
| GET | `/api/sources/{id}/chapters?url=` | 目录 |
| GET | `/api/sources/{id}/content?url=` | 章节图片列表 |
| GET | `/api/image?url=&source_id=&headers=` | 图片代理（自动带 Referer/UA） |

## App

```bash
cd app
flutter run            # 或 flutter build apk
```

底部四个页面：发现 / 搜索 / 书源 / 设置。阅读器支持翻页（左→右、右→左）和条漫滚动，阅读进度存在本机。

后端地址在「设置」里改：模拟器默认 `http://10.0.2.2:8090`，真机填电脑的局域网 IP。
