from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import analytics, feed, outreach, pipeline
from app.db import init_db
from app.scheduler import run_all_enabled, start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Running initial ingestion pass for enabled sources...")
    try:
        run_all_enabled()
    except Exception:
        logger.exception("Initial ingestion pass failed; dashboard will still start")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI/LLM Job Crawler", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(feed.router)
app.include_router(pipeline.router)
app.include_router(outreach.router)
app.include_router(analytics.router)
