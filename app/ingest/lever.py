"""Lever public postings API driver.

Docs: https://github.com/lever/postings-api
Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
"""
from __future__ import annotations

import datetime as dt
import json
import logging

import httpx

from app.config import get_companies
from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)

API_URL = "https://api.lever.co/v0/postings/{slug}"


class LeverDriver(IngestDriver):
    source_name = "lever"

    def fetch(self) -> list[RawPosting]:
        postings: list[RawPosting] = []
        companies = [c for c in get_companies() if c.get("board") == "lever"]
        with httpx.Client(timeout=20) as client:
            for company in companies:
                slug = company["slug"]
                try:
                    resp = client.get(API_URL.format(slug=slug), params={"mode": "json"})
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Lever fetch failed for %s: %s", slug, exc)
                    continue

                for job in resp.json():
                    posting = self._normalize(company["name"], job)
                    if posting:
                        postings.append(posting)
        return postings

    def _normalize(self, company_name: str, job: dict) -> RawPosting | None:
        title = job.get("text")
        if not title:
            return None

        categories = job.get("categories") or {}
        location = categories.get("location")
        commitment = (categories.get("commitment") or "").lower()
        work_mode = "remote" if "remote" in (location or "").lower() else "unknown"

        posted_date = None
        created_at = job.get("createdAt")
        if created_at:
            try:
                posted_date = dt.datetime.fromtimestamp(created_at / 1000, tz=dt.timezone.utc).replace(tzinfo=None)
            except (TypeError, ValueError, OSError):
                pass

        description = job.get("descriptionPlain") or job.get("description") or ""

        return RawPosting(
            title=title,
            company=company_name,
            source_name=self.source_name,
            source_url=job.get("hostedUrl", ""),
            location=location,
            work_mode=work_mode,
            posted_date=posted_date,
            description=f"{description}\n{commitment}",
            raw_payload=json.dumps(job)[:20000],
        )
