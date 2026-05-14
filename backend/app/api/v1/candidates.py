from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.candidate import CandidateListResponse, CandidateResponse, ScoreBreakdown
from app.services import request_service

router = APIRouter(tags=["Candidates"])


@router.get("/requests/{request_id}/candidates", response_model=CandidateListResponse)
def get_candidates(
    request_id: int,
    platform: str | None = Query(None, description="Filter by platform (e.g. linkedin)"),
    min_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    req = request_service.get_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    candidates, total = request_service.get_candidates(
        db, request_id, platform=platform, min_score=min_score, limit=limit, offset=offset
    )

    items = []
    for c in candidates:
        breakdown = None
        if c.score_breakdown:
            breakdown = ScoreBreakdown(
                skills_score=c.score_breakdown.get("skills_score", 0),
                experience_score=c.score_breakdown.get("experience_score", 0),
                location_score=c.score_breakdown.get("location_score", 0),
                keywords_score=c.score_breakdown.get("keywords_score", 0),
            )
        items.append(
            CandidateResponse(
                id=c.id,
                rank=c.rank,
                platform=c.platform,
                full_name=c.full_name,
                headline=c.headline,
                location=c.location,
                experience_years=float(c.experience_years) if c.experience_years is not None else None,
                skills=c.skills or [],
                profile_url=c.profile_url,
                summary=c.summary,
                suitability_score=float(c.suitability_score) if c.suitability_score is not None else None,
                score_breakdown=breakdown,
                email=c.email,
                email_status=c.email_status,
                email_sent=c.email_sent,
                created_at=c.created_at,
            )
        )

    return CandidateListResponse(
        items=items,
        total=total,
        request_status=req.status,
    )
