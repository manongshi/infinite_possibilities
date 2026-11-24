"""API 冒烟测试（不联网）：书源导入 / 列表 / 启停 / 修改 / 删除。"""
import json
import os
import tempfile
from pathlib import Path

os.environ["INFINITE_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SEED = json.loads((Path(__file__).resolve().parent.parent / "seeds" / "manhuagui.json").read_text("utf-8"))


def test_sources_crud():
    with TestClient(app) as c:
        lst = c.get("/api/sources").json()
        assert len(lst) == 1 and lst[0]["source_type"] == "comic" and lst[0]["format"] == "legacy"
        sid = lst[0]["id"]

        # 再次导入同一 bookSourceUrl -> 覆盖而不是新增
        r = c.post("/api/sources", json=[SEED, {"bookSourceName": "x"}]).json()
        assert r["created"] == 0 and r["updated"] == 1 and len(r["errors"]) == 1

        assert c.patch(f"/api/sources/{sid}/enabled", json={"enabled": False}).json()["enabled"] is False
        assert c.get(f"/api/sources/{sid}/json").json()["enable"] is False

        changed = dict(SEED, bookSourceName="看漫画2")
        assert c.put(f"/api/sources/{sid}", json=changed).json()["name"] == "看漫画2"

        kinds = c.get(f"/api/sources/{sid}/explore").json()
        assert kinds[0]["title"] == "最近更新"

        assert c.delete(f"/api/sources/{sid}").json()["ok"]
        assert c.get("/api/sources").json() == []
