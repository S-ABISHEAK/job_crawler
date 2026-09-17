from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import LEVEL_TAGS, PIPELINE_STAGES, AppState, Posting
from app.scheduler import run_all_enabled
from app.templating import templates

router = APIRouter()

LAST_VISIT_KEY = "feed_last_visit_at"


def _location_bucket(location: str | None, work_mode: str) -> str:
    loc = (location or "").lower()
    if work_mode == "remote" or "remote" in loc:
        return "remote"
    if "chennai" in loc:
        return "chennai"
    if "bangalore" in loc or "bengaluru" in loc:
        return "bangalore"
    return "other"


def _apply_filters(
    postings: list[Posting],
    level: str,
    location: str,
    source: str,
    role: str,
    show_red_flags: bool,
) -> list[Posting]:
    if level and level != "all":
        postings = [p for p in postings if p.level_tag == level]
    if location:
        postings = [p for p in postings if _location_bucket(p.location, p.work_mode) == location]
    if source:
        postings = [p for p in postings if any(su.source_name == source for su in p.source_urls)]
    if role:
        role_lower = role.lower()
        postings = [p for p in postings if role_lower in p.title.lower()]
    if not show_red_flags:
        postings = [p for p in postings if not p.red_flag]
    return postings


def _touch_last_visit(db: Session) -> dt.datetime | None:
    """Reads the previous last-visit timestamp, then bumps it to now.
    Returns the previous value (used to compute "new since last visit")."""
    last_visit_row = db.get(AppState, LAST_VISIT_KEY)
    last_visit = dt.datetime.fromisoformat(last_visit_row.value) if last_visit_row and last_visit_row.value else None

    if last_visit_row is None:
        last_visit_row = AppState(key=LAST_VISIT_KEY)
        db.add(last_visit_row)
    last_visit_row.value = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()

    return last_visit


@router.get("/")
def companies_view(
    request: Request,
    level: str | None = None,
    location: str = "",
    source: str = "",
    role: str = "",
    show_red_flags: bool = False,
    db: Session = Depends(get_db),
):
    # Default to internships on first load -- this crawler exists to find
    # you intern roles first. Pass level=all explicitly to see everything.
    effective_level = level if level is not None else "intern"

    last_visit = _touch_last_visit(db)

    all_postings = list(db.scalars(select(Posting).order_by(Posting.relevance_score.desc())))
    postings = _apply_filters(all_postings, effective_level, location, source, role, show_red_flags)

    new_ids = {p.id for p in postings if last_visit is None or p.first_seen_at > last_visit}

    by_company: dict[str, list[Posting]] = defaultdict(list)
    for p in postings:
        by_company[p.company].append(p)

    companies = [
        {
            "name": name,
            "count": len(plist),
            "top_score": max(p.relevance_score for p in plist),
            "has_new": any(p.id in new_ids for p in plist),
        }
        for name, plist in by_company.items()
    ]
    companies.sort(key=lambda c: c["top_score"], reverse=True)

    source_options = sorted({su.source_name for p in all_postings for su in p.source_urls})

    return templates.TemplateResponse(
        request,
        "companies.html",
        {
            "active": "companies",
            "companies": companies,
            "total_matching": len(postings),
            "level_options": LEVEL_TAGS,
            "source_options": source_options,
            "filters": {
                "level": effective_level,
                "location": location,
                "source": source,
                "role": role,
                "show_red_flags": show_red_flags,
            },
        },
    )


@router.get("/companies/{company_name}/jobs")
def company_jobs_view(
    request: Request,
    company_name: str,
    level: str | None = None,
    location: str = "",
    source: str = "",
    role: str = "",
    show_red_flags: bool = False,
    db: Session = Depends(get_db),
):
    effective_level = level if level is not None else "intern"

    postings = list(
        db.scalars(
            select(Posting).where(Posting.company == company_name).order_by(Posting.relevance_score.desc())
        )
    )
    postings = _apply_filters(postings, effective_level, location, source, role, show_red_flags)

    source_options = sorted({su.source_name for p in postings for su in p.source_urls})

    return templates.TemplateResponse(
        request,
        "company_jobs.html",
        {
            "active": "companies",
            "company_name": company_name,
            "postings": postings,
            "level_options": LEVEL_TAGS,
            "source_options": source_options,
            "pipeline_stages": PIPELINE_STAGES,
            "filters": {
                "level": effective_level,
                "location": location,
                "source": source,
                "role": role,
                "show_red_flags": show_red_flags,
            },
        },
    )


@router.post("/refresh")
def refresh():
    run_all_enabled()
    return RedirectResponse(url="/", status_code=303)


@router.post("/postings/{posting_id}/status")
def update_status(posting_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    posting = db.get(Posting, posting_id)
    if not posting:
        return {"ok": False, "error": "not found"}
    status = payload.get("status")
    if status not in PIPELINE_STAGES:
        return {"ok": False, "error": "invalid status"}
    posting.pipeline_status = status
    return {"ok": True}
