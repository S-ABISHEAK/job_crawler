#!/usr/bin/env python3
"""Company discovery/verification tool.

Problem this solves: hand-guessing Greenhouse/Lever/Ashby slugs for new
companies is slow and mostly wrong. Instead, add company *names* to
config/candidate_companies.yaml (no slug/board guessing needed) and run
this script -- it tries a set of slug variants for each name against all
three board APIs and reports which ones actually resolve to a real,
live job board. Only confirmed hits are worth trusting.

Usage:
    python scripts/verify_companies.py                 # dry run, report only
    python scripts/verify_companies.py --append         # also write confirmed
                                                          # matches into
                                                          # config/companies.yaml

Note: many India/France startups don't publish via Greenhouse/Lever/Ashby
at all (Workday, SmartRecruiters, Welcome to the Jungle, or a custom
careers page are common instead). Those will report as "no match" here --
that's expected, not a bug. They'd need a dedicated RSS or scrape source
instead (see README).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = ROOT / "config" / "candidate_companies.yaml"
COMPANIES_PATH = ROOT / "config" / "companies.yaml"

BOARD_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}

SUFFIXES_TO_STRIP = ["technologies", "technology", "labs", "ai", "the", "inc"]

REQUEST_DELAY_SECONDS = 0.5  # be polite -- these are small companies' own APIs


def slug_variants(name: str) -> list[str]:
    base = name.lower().strip()
    base = re.sub(r"\.(ai|io|com|tt|sh)$", "", base)  # strip trailing domain-like suffix
    alnum = re.sub(r"[^a-z0-9\s-]", "", base)
    words = alnum.split()

    variants = set()
    variants.add("".join(words))
    variants.add("-".join(words))

    stripped_words = [w for w in words if w not in SUFFIXES_TO_STRIP]
    if stripped_words and stripped_words != words:
        variants.add("".join(stripped_words))
        variants.add("-".join(stripped_words))

    return [v for v in variants if v]


def check_slug(client: httpx.Client, board: str, slug: str) -> int | None:
    """Returns job count if the slug resolves to a real board, else None."""
    url = BOARD_URLS[board].format(slug=slug)
    try:
        resp = client.get(url, timeout=15)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    if board in ("greenhouse", "ashby"):
        jobs = data.get("jobs") if isinstance(data, dict) else None
        return len(jobs) if isinstance(jobs, list) else None
    if board == "lever":
        return len(data) if isinstance(data, list) else None
    return None


def load_existing_slugs() -> set[tuple[str, str]]:
    with open(COMPANIES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {(c["board"], c["slug"]) for c in data.get("companies", [])}


def append_to_companies_yaml(matches: list[dict]) -> None:
    """Appends confirmed entries as text, preserving the existing file's
    comments/formatting instead of re-serializing the whole thing."""
    lines = []
    for m in matches:
        lines.append(f"  - name: {m['name']}")
        lines.append(f"    board: {m['board']}")
        lines.append(f"    slug: {m['slug']}")
        lines.append(f"    notes: auto-discovered via verify_companies.py, {m['jobs']} live jobs at check time")
        lines.append("")
    with open(COMPANIES_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", action="store_true", help="Write confirmed matches into config/companies.yaml")
    args = parser.parse_args()

    with open(CANDIDATES_PATH, "r", encoding="utf-8") as f:
        candidates = (yaml.safe_load(f) or {}).get("candidates", [])

    existing = load_existing_slugs()

    matches: list[dict] = []
    unmatched: list[str] = []

    with httpx.Client() as client:
        for candidate in candidates:
            name = candidate["name"]
            found = False
            for slug in slug_variants(name):
                for board in ("greenhouse", "lever", "ashby"):
                    if (board, slug) in existing:
                        continue
                    job_count = check_slug(client, board, slug)
                    time.sleep(REQUEST_DELAY_SECONDS)
                    if job_count is not None:
                        print(f"MATCH  {name:30s} -> {board}/{slug}  ({job_count} jobs)")
                        matches.append({"name": name, "board": board, "slug": slug, "jobs": job_count})
                        found = True
                        break
                if found:
                    break
            if not found:
                unmatched.append(name)
                print(f"no match  {name}")

    print(f"\n{len(matches)} confirmed, {len(unmatched)} unmatched (likely not on Greenhouse/Lever/Ashby)")

    if args.append and matches:
        append_to_companies_yaml(matches)
        print(f"Appended {len(matches)} entries to {COMPANIES_PATH}")
    elif matches:
        print("Re-run with --append to write these into config/companies.yaml")

    return 0


if __name__ == "__main__":
    sys.exit(main())
