"""Common normalized posting shape every ingest driver must produce."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class RawPosting:
    """One job posting, normalized to a common shape before scoring/dedup."""

    title: str
    company: str
    source_name: str
    source_url: str
    location: str | None = None
    work_mode: str = "unknown"  # remote / onsite / hybrid / unknown
    stipend_raw: str | None = None
    posted_date: dt.datetime | None = None
    description: str = ""
    raw_payload: str = ""  # original JSON/text, kept for debugging

    def stable_id(self) -> str:
        """Deterministic id from normalized (company, title, location) so
        re-ingestion of the same posting produces the same id."""
        key = self.dedup_key()
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    def dedup_key(self) -> str:
        def norm(s: str | None) -> str:
            s = (s or "").lower().strip()
            s = re.sub(r"[^a-z0-9]+", " ", s)
            return re.sub(r"\s+", " ", s).strip()

        return f"{norm(self.company)}|{norm(self.title)}|{norm(self.location)}"


class IngestDriver:
    """Subclass and implement fetch() to add a new source type."""

    source_name: str = "base"

    def fetch(self) -> list[RawPosting]:
        raise NotImplementedError
