from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Posting
from app.templating import templates

router = APIRouter()

APPLIED_STATUSES = {"Applied", "Outreach Sent", "Replied", "Interview", "Offer", "Rejected"}
REPLIED_STATUSES = {"Replied", "Interview", "Offer"}
INTERVIEW_STATUSES = {"Interview", "Offer"}
OFFER_STATUSES = {"Offer"}


def _bucket_counts(postings: list[Posting]) -> dict:
    return {
        "applied": sum(1 for p in postings if p.pipeline_status in APPLIED_STATUSES),
        "replied": sum(1 for p in postings if p.pipeline_status in REPLIED_STATUSES),
        "interview": sum(1 for p in postings if p.pipeline_status in INTERVIEW_STATUSES),
        "offer": sum(1 for p in postings if p.pipeline_status in OFFER_STATUSES),
    }


@router.get("/analytics")
def analytics_view(request: Request, db: Session = Depends(get_db)):
    postings = list(db.scalars(select(Posting)))

    totals = _bucket_counts(postings)

    by_source_postings: dict[str, list[Posting]] = defaultdict(list)
    for p in postings:
        source_names = {su.source_name for su in p.source_urls} or {p.primary_source_name or "unknown"}
        for name in source_names:
            by_source_postings[name].append(p)

    by_source = [
        {"source": name, "total": len(plist), **{k: v for k, v in _bucket_counts(plist).items() if k in ("applied", "interview", "offer")}}
        for name, plist in sorted(by_source_postings.items())
    ]

    with_outreach = [p for p in postings if p.outreach_entries]
    without_outreach = [p for p in postings if not p.outreach_entries]

    outreach_split = {
        "with_outreach": _bucket_counts(with_outreach),
        "without_outreach": _bucket_counts(without_outreach),
    }

    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "active": "analytics",
            "totals": totals,
            "by_source": by_source,
            "outreach_split": outreach_split,
        },
    )
