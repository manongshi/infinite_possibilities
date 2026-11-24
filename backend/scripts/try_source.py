"""命令行跑一遍书源全流程：python scripts/try_source.py seeds/manhuagui.json 关键词"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine import book  # noqa: E402
from app.engine.request import close_client  # noqa: E402
from app.engine.source import parse_source  # noqa: E402


async def main(path: str, key: str) -> None:
    src = parse_source(json.loads(Path(path).read_text("utf-8")))
    print(f"[源] {src.name} ({src.format}, {src.type})")
    kinds = book.explore_kinds(src)
    print(f"[发现] {len(kinds)} 个分类: {[k.title for k in kinds]}")
    if kinds:
        items, more = await book.explore(src, kinds[0].url, 1)
        print(f"[发现/{kinds[0].title}] {len(items)} 本, more={more}; 第一本: {items[0] if items else None}")
    results = await book.search(src, key)
    print(f"[搜索 {key}] {len(results)} 条")
    for b in results[:3]:
        print("   ", b.name, b.author, b.book_url, b.cover_url)
    if not results:
        return
    info = await book.book_info(src, results[0].book_url)
    print(f"[详情] {info.name} / {info.author} / cover={info.cover_url}\n    intro={info.intro[:60]}…")
    chs = await book.chapter_list(src, info.toc_url)
    print(f"[目录] {len(chs)} 章: {[c.title for c in chs[:3]]} … {[c.title for c in chs[-2:]]}")
    if chs:
        c = await book.content(src, chs[0].url, chs[1].url if len(chs) > 1 else "")
        print(f"[正文] {chs[0].title}: {len(c.images)} 张图")
        for img in c.images[:2]:
            print("   ", img.url, img.headers.get("Referer"))
    await close_client()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "海贼"))
