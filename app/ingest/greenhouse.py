"""Greenhouse public job board API driver.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
"""
from __future__ import annotations

import datetime as dt
import json
import logging

import httpx

from app.config import get_companies
from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)

API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseDriver(IngestDriver):
    source_name = "greenhouse"

    def fetch(self) -> list[RawPosting]:
        postings: list[RawPosting] = []
        companies = [c for c in get_companies() if c.get("board") == "greenhouse"]
        with httpx.Client(timeout=20) as client:
            for company in companies:
                slug = company["slug"]
                try:
                    resp = client.get(API_URL.format(slug=slug), params={"content": "true"})
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Greenhouse fetch failed for %s: %s", slug, exc)
                    continue

                data = resp.json()
                for job in data.get("jobs", []):
                    posting = self._normalize(company["name"], job)
                    if posting:
                        postings.append(posting)
        return postings

    def _normalize(self, company_name: str, job: dict) -> RawPosting | None:
        title = job.get("title")
        if not title:
            return None

        location = None
        loc_obj = job.get("location") or {}
        if isinstance(loc_obj, dict):
            location = loc_obj.get("name")

        posted_date = None
        updated_at = job.get("updated_at")
        if updated_at:
            try:
                posted_date = dt.datetime.fromisoformat(updated_at.replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
            except ValueError:
                pass

        return RawPosting(
            title=title,
            company=company_name,
            source_name=self.source_name,
            source_url=job.get("absolute_url", ""),
            location=location,
            posted_date=posted_date,
            description=job.get("content", "") or "",
            raw_payload=json.dumps(job)[:20000],
        )
