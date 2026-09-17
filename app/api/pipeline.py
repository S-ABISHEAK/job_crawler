from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PIPELINE_STAGES, Posting
from app.templating import templates

router = APIRouter()


@router.get("/pipeline")
def pipeline_view(request: Request, db: Session = Depends(get_db)):
    postings = list(db.scalars(select(Posting).order_by(Posting.relevance_score.desc())))

    by_stage: dict[str, list[Posting]] = {stage: [] for stage in PIPELINE_STAGES}
    for p in postings:
        by_stage.setdefault(p.pipeline_status, []).append(p)

    return templates.TemplateResponse(
        request,
        "pipeline.html",
        {
            "active": "pipeline",
            "pipeline_stages": PIPELINE_STAGES,
            "by_stage": by_stage,
        },
    )
