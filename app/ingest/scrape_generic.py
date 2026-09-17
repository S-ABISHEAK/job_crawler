"""Placeholder for low-priority scrape sources (Wellfound, Cutshort, Instahyre,
Hirist, Internshala, Unstop).

These are disabled by default in config/sources.yaml (enabled: false).
Before enabling any of them:
  1. Fetch and read that site's /robots.txt yourself.
  2. If disallowed for the paths you'd need, leave it disabled -- treat as
     a manual-check source instead.
  3. If allowed, implement a per-site parser here (site markup varies too
     much for one generic scraper to handle reliably) and keep the site's
     own poll_interval, which is already set conservatively (1-2x/day).

This module intentionally does not perform any live scraping yet -- it
exists as the wiring point so enabling a site later is a small, isolated
change instead of new plumbing.
"""
from __future__ import annotations

import logging

from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)


class ScrapeGenericDriver(IngestDriver):
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.source_name = name

    def fetch(self) -> list[RawPosting]:
        logger.info(
            "Scrape source '%s' is a stub (no site-specific parser implemented yet). "
            "Verify robots.txt at %s/robots.txt before implementing.",
            self.name,
            self.url.rstrip("/"),
        )
        return []
