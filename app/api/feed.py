from __future__ import annotations

import datetime as dt

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


@router.get("/")
def feed(
    request: Request,
    level: str = "",
    location: str = "",
    source: str = "",
    show_red_flags: bool = False,
    db: Session = Depends(get_db),
):
    last_visit_row = db.get(AppState, LAST_VISIT_KEY)
    last_visit = dt.datetime.fromisoformat(last_visit_row.value) if last_visit_row and last_visit_row.value else None

    postings = list(db.scalars(select(Posting).order_by(Posting.relevance_score.desc())))

    if level:
        postings = [p for p in postings if p.level_tag == level]
    if location:
        postings = [p for p in postings if _location_bucket(p.location, p.work_mode) == location]
    if source:
        postings = [p for p in postings if any(su.source_name == source for su in p.source_urls)]
    if not show_red_flags:
        postings = [p for p in postings if not p.red_flag]

    new_ids = {p.id for p in postings if last_visit is None or p.first_seen_at > last_visit}

    source_options = sorted({su.source_name for p in postings for su in p.source_urls})

    if last_visit_row is None:
        last_visit_row = AppState(key=LAST_VISIT_KEY)
        db.add(last_visit_row)
    last_visit_row.value = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()

    return templates.TemplateResponse(
        request,
        "feed.html",
        {
            "active": "feed",
            "postings": postings,
            "new_ids": new_ids,
            "level_options": LEVEL_TAGS,
            "source_options": source_options,
            "pipeline_stages": PIPELINE_STAGES,
            "filters": {
                "level": level,
                "location": location,
                "source": source,
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
