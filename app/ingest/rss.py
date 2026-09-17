"""Generic RSS/Atom polling driver for Tier 2 niche AI/LLM job boards.

Each source entry in config/sources.yaml with type: rss and a `url` is
polled with feedparser. Respect the source's poll_interval -- this driver
does not rate-limit itself beyond what the scheduler already enforces.
"""
from __future__ import annotations

import datetime as dt
import logging

import feedparser

from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)


class RSSDriver(IngestDriver):
    source_name = "rss"

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.source_name = name

    def fetch(self) -> list[RawPosting]:
        parsed = feedparser.parse(self.url)
        if parsed.bozo:
            logger.warning("RSS feed %s (%s) failed to parse cleanly: %s", self.name, self.url, parsed.bozo_exception)

        postings: list[RawPosting] = []
        for entry in parsed.entries:
            title = entry.get("title")
            link = entry.get("link")
            if not title or not link:
                continue

            posted_date = None
            if entry.get("published_parsed"):
                posted_date = dt.datetime(*entry.published_parsed[:6])

            postings.append(
                RawPosting(
                    title=title,
                    company=entry.get("author", "Unknown"),
                    source_name=self.name,
                    source_url=link,
                    posted_date=posted_date,
                    description=entry.get("summary", ""),
                    raw_payload=str(entry)[:20000],
                )
            )
        return postings
