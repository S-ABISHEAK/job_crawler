"""Orchestrates one ingestion pass: fetch -> raw log -> dedup -> score -> persist.

Used by both the scheduler (automatic polling) and manual "refresh now"
triggers from the dashboard.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.dedup import find_matching_posting
from app.ingest.base import IngestDriver, RawPosting
from app.models import Posting, RawIngestLog, SourceURL
from app.scoring import compute_score, infer_level_tag, infer_work_mode

logger = logging.getLogger(__name__)


def run_driver(session: Session, driver: IngestDriver) -> dict:
    """Runs one driver's fetch(), persists results, returns a summary dict."""
    try:
        raw_postings = driver.fetch()
    except Exception:
        logger.exception("Driver %s failed", driver.source_name)
        return {"source": driver.source_name, "fetched": 0, "new": 0, "updated": 0, "error": True}

    new_count = 0
    updated_count = 0

    for raw in raw_postings:
        session.add(
            RawIngestLog(source_name=raw.source_name, payload=raw.raw_payload[:20000])
        )
        is_new = _upsert_posting(session, raw)
        if is_new:
            new_count += 1
        else:
            updated_count += 1

    session.flush()
    logger.info(
        "%s: fetched=%d new=%d updated=%d", driver.source_name, len(raw_postings), new_count, updated_count
    )
    return {
        "source": driver.source_name,
        "fetched": len(raw_postings),
        "new": new_count,
        "updated": updated_count,
        "error": False,
    }


def _upsert_posting(session: Session, raw: RawPosting) -> bool:
    """Returns True if a new Posting row was created, False if an existing
    one was matched/updated."""
    existing = find_matching_posting(session, raw)

    level_tag = infer_level_tag(raw.title, raw.description)
    work_mode = infer_work_mode(raw.location, raw.description, raw.work_mode)
    score, red_flag, red_flag_reason = compute_score(
        raw.title, raw.description, raw.location, work_mode, level_tag
    )

    if existing:
        existing.relevance_score = score
        existing.red_flag = red_flag
        existing.red_flag_reason = red_flag_reason
        existing.level_tag = level_tag
        existing.work_mode = work_mode
        if raw.description and not existing.description:
            existing.description = raw.description
        _attach_source_url(session, existing.id, raw)
        return False

    posting = Posting(
        id=raw.stable_id(),
        title=raw.title,
        company=raw.company,
        location=raw.location,
        work_mode=work_mode,
        stipend_raw=raw.stipend_raw,
        posted_date=raw.posted_date,
        description=raw.description,
        level_tag=level_tag,
        relevance_score=score,
        red_flag=red_flag,
        red_flag_reason=red_flag_reason,
        primary_source_name=raw.source_name,
        dedup_key=raw.dedup_key(),
    )
    session.add(posting)
    session.flush()
    _attach_source_url(session, posting.id, raw)
    return True


def _attach_source_url(session: Session, posting_id: str, raw: RawPosting) -> None:
    exists = (
        session.query(SourceURL)
        .filter_by(posting_id=posting_id, source_name=raw.source_name, url=raw.source_url)
        .first()
    )
    if exists:
        return
    session.add(
        SourceURL(
            posting_id=posting_id,
            source_name=raw.source_name,
            url=raw.source_url,
            raw_json=raw.raw_payload[:20000],
        )
    )
