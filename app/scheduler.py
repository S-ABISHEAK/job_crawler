"""Builds one IngestDriver per enabled source in config/sources.yaml and
polls each on its own configured interval via APScheduler.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_sources
from app.db import get_session
from app.ingest.ashby import AshbyDriver
from app.ingest.base import IngestDriver
from app.ingest.email_gmail import GmailAlertDriver
from app.ingest.greenhouse import GreenhouseDriver
from app.ingest.lever import LeverDriver
from app.ingest.rss import RSSDriver
from app.ingest.scrape_generic import ScrapeGenericDriver
from app.pipeline import run_driver

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def build_driver(source: dict) -> IngestDriver | None:
    name = source["name"]
    source_type = source["type"]

    if source_type == "api":
        return {
            "greenhouse": GreenhouseDriver,
            "lever": LeverDriver,
            "ashby": AshbyDriver,
        }.get(name, lambda: None)()
    if source_type == "rss":
        return RSSDriver(name=name, url=source["url"])
    if source_type == "scrape":
        return ScrapeGenericDriver(name=name, url=source["url"])
    if source_type == "email-parse":
        return GmailAlertDriver()

    logger.warning("Unknown source type '%s' for source '%s'", source_type, name)
    return None


def poll_source(source: dict) -> dict:
    driver = build_driver(source)
    if driver is None:
        return {"source": source["name"], "fetched": 0, "new": 0, "updated": 0, "error": True}
    with get_session() as session:
        return run_driver(session, driver)


def run_all_enabled(sources: list[dict] | None = None) -> list[dict]:
    """Runs every enabled source once, synchronously. Used for manual
    "refresh now" and for the first population on startup."""
    results = []
    for source in sources or get_sources():
        if source.get("enabled", True) is False:
            continue
        results.append(poll_source(source))
    return results


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler()
    for source in get_sources():
        if source.get("enabled", True) is False:
            continue
        interval_minutes = source.get("poll_interval", 240)
        scheduler.add_job(
            poll_source,
            "interval",
            minutes=interval_minutes,
            args=[source],
            id=f"poll_{source['name']}",
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
