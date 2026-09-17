"""Ashby public job board API driver.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}
(Unofficial but widely used public endpoint; verify per-company as Ashby's
public API surface has changed over time.)
"""
from __future__ import annotations

import datetime as dt
import json
import logging

import httpx

from app.config import get_companies
from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbyDriver(IngestDriver):
    source_name = "ashby"

    def fetch(self) -> list[RawPosting]:
        postings: list[RawPosting] = []
        companies = [c for c in get_companies() if c.get("board") == "ashby"]
        with httpx.Client(timeout=20) as client:
            for company in companies:
                slug = company["slug"]
                try:
                    resp = client.get(API_URL.format(slug=slug), params={"includeCompensation": "true"})
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Ashby fetch failed for %s: %s", slug, exc)
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

        location = job.get("location") or job.get("addressLocality")
        work_mode = "remote" if job.get("isRemote") else "unknown"

        posted_date = None
        published_at = job.get("publishedAt")
        if published_at:
            try:
                posted_date = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
            except ValueError:
                pass

        description = job.get("descriptionPlain") or job.get("descriptionHtml") or ""

        return RawPosting(
            title=title,
            company=company_name,
            source_name=self.source_name,
            source_url=job.get("jobUrl") or job.get("applyUrl") or "",
            location=location,
            work_mode=work_mode,
            posted_date=posted_date,
            description=description,
            raw_payload=json.dumps(job)[:20000],
        )
