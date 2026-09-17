from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OutreachLog, Posting
from app.templating import templates

router = APIRouter()


@router.get("/outreach")
def outreach_view(request: Request, db: Session = Depends(get_db)):
    postings = list(db.scalars(select(Posting).order_by(Posting.relevance_score.desc())))

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for p in postings:
        for entry in p.outreach_entries:
            if entry.date_messaged:
                delta = now - entry.date_messaged
                entry.days_since_messaged = delta.days
            else:
                entry.days_since_messaged = 0

    return templates.TemplateResponse(
        request,
        "outreach.html",
        {"active": "outreach", "postings": postings},
    )


@router.post("/postings/{posting_id}/outreach")
def add_outreach_entry(posting_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    posting = db.get(Posting, posting_id)
    if not posting:
        return {"ok": False, "error": "not found"}

    date_messaged = None
    if payload.get("date_messaged"):
        try:
            date_messaged = dt.datetime.fromisoformat(payload["date_messaged"])
        except ValueError:
            date_messaged = None

    entry = OutreachLog(
        posting_id=posting_id,
        contact_name=payload.get("contact_name") or None,
        channel=payload.get("channel") or None,
        date_messaged=date_messaged,
        notes=payload.get("notes") or None,
    )
    db.add(entry)
    if posting.pipeline_status == "New" or posting.pipeline_status == "Reviewed":
        posting.pipeline_status = "Outreach Sent"

    return {"ok": True}
