from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import comic, sources
from .db import SessionLocal, init_db
from .engine.request import close_client
from .services import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_if_empty(db)
    yield
    await close_client()


app = FastAPI(title="Infinite Reader API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(sources.router)
app.include_router(comic.router)


@app.get("/api/health")
def health():
    return {"ok": True}
