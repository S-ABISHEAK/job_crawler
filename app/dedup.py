"""Fuzzy dedup: merges postings that are the same role reposted across
multiple boards into one record with all source URLs attached.
"""
from __future__ import annotations

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.base import RawPosting
from app.models import Posting

TITLE_MATCH_THRESHOLD = 88  # rapidfuzz token_sort_ratio, 0-100


def find_matching_posting(session: Session, raw: RawPosting) -> Posting | None:
    """Exact dedup_key match first (cheap, catches the common case),
    then a fuzzy fallback scoped to the same company."""
    exact_id = raw.stable_id()
    existing = session.get(Posting, exact_id)
    if existing:
        return existing

    candidates = session.scalars(
        select(Posting).where(Posting.company == raw.company)
    ).all()

    for candidate in candidates:
        title_similarity = fuzz.token_sort_ratio(raw.title.lower(), candidate.title.lower())
        if title_similarity < TITLE_MATCH_THRESHOLD:
            continue

        same_location = (
            (raw.location or "").strip().lower() == (candidate.location or "").strip().lower()
            or raw.work_mode == "remote"
            or candidate.work_mode == "remote"
        )
        if same_location:
            return candidate

    return None
