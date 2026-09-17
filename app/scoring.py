"""Weighted relevance scoring, level/location inference, and red-flag
detection. All weights come from config/keywords.yaml and
config/scoring.yaml -- tune there, not here.
"""
from __future__ import annotations

import re

from app.config import get_keywords, get_scoring

LEVEL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\bintern(ship)?\b", re.I)),
    ("fresher", re.compile(r"\bfresher\b", re.I)),
    ("0-1yr", re.compile(r"\b0[\s-]*(to|-)?\s*1\+?\s*year", re.I)),
    ("1-2yr", re.compile(r"\b1[\s-]*(to|-)?\s*2\+?\s*year", re.I)),
    ("2+yr", re.compile(r"\b([2-9]|\d{2})\+?\s*year", re.I)),
]

REMOTE_PATTERN = re.compile(r"\bremote\b", re.I)
HYBRID_PATTERN = re.compile(r"\bhybrid\b", re.I)
ONSITE_PATTERN = re.compile(r"\b(on[\s-]?site|in[\s-]?office)\b", re.I)


def infer_level_tag(title: str, description: str) -> str:
    text = f"{title}\n{description}"
    for tag, pattern in LEVEL_PATTERNS:
        if pattern.search(text):
            return tag
    return "unknown"


def infer_work_mode(location: str | None, description: str, existing: str = "unknown") -> str:
    if existing and existing != "unknown":
        return existing
    text = f"{location or ''}\n{description}"
    if REMOTE_PATTERN.search(text):
        return "remote"
    if HYBRID_PATTERN.search(text):
        return "hybrid"
    if ONSITE_PATTERN.search(text):
        return "onsite"
    return "unknown"


def _location_bucket(location: str | None, work_mode: str) -> str:
    loc = (location or "").lower()
    if work_mode == "remote" or "remote" in loc:
        return "remote"
    if "chennai" in loc:
        return "chennai"
    if "bangalore" in loc or "bengaluru" in loc:
        return "bangalore"
    if "india" in loc:
        return "other_india"
    return "other"


def score_keywords(title: str, description: str) -> float:
    text = f"{title}\n{description}".lower()
    keywords = get_keywords()
    total = 0.0
    for _group_name, group in keywords.items():
        weight = group.get("weight", 0)
        for term in group.get("terms", []):
            if term.lower() in text:
                total += weight
    return total


def detect_red_flag(title: str, description: str) -> tuple[bool, str | None]:
    text = f"{title}\n{description}".lower()
    scoring = get_scoring()
    patterns = scoring.get("red_flags", {}).get("patterns", {})
    for phrase, reason in patterns.items():
        if phrase.lower() in text:
            return True, reason
    return False, None


def compute_score(
    title: str,
    description: str,
    location: str | None,
    work_mode: str,
    level_tag: str,
) -> tuple[float, bool, str | None]:
    """Returns (relevance_score, red_flag, red_flag_reason)."""
    scoring = get_scoring()
    score = float(scoring.get("base_score", 0))

    score += score_keywords(title, description)
    score += scoring.get("level", {}).get(level_tag, 0)

    bucket = _location_bucket(location, work_mode)
    score += scoring.get("location", {}).get(bucket, 0)

    red_flag, reason = detect_red_flag(title, description)
    if red_flag:
        score += scoring.get("red_flags", {}).get("penalty", 0)

    return score, red_flag, reason
