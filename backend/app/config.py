"""全局配置。都可以用环境变量覆盖，方便以后换数据库 / 部署。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("INFINITE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 目前用本地 SQLite；以后换 MySQL/Postgres 只需改这个 URL
DATABASE_URL = os.getenv("INFINITE_DATABASE_URL", f"sqlite:///{DATA_DIR / 'infinite.db'}")

# 首次启动时自动导入的书源目录
SEED_DIR = Path(os.getenv("INFINITE_SEED_DIR", BASE_DIR / "seeds"))

HTTP_TIMEOUT = float(os.getenv("INFINITE_HTTP_TIMEOUT", "20"))
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36"
)
