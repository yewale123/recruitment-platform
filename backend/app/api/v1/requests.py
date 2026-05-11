from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.recruitment_request import (
    RecruitmentRequestCreate,
    RecruitmentRequestResponse,
    RecruitmentRequestListResponse,
    RecruitmentRequestListItem,
    ScrapeJobSummary,
)
from app.services import request_service
from app.tasks.scrape_tasks import run_recruitment_scrape

router = APIRouter(prefix="/requests", tags=["Requests"])


@router.post("", response_model=RecruitmentRequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(data: RecruitmentRequestCreate, db: Session = Depends(get_db)):
    req = request_service.create_request(db, data)
    # Fire and forget — Celery picks it up asynchronously
    run_recruitment_scrape.delay(req.id)
    return _to_response(req)


@router.get("", response_model=RecruitmentRequestListResponse)
def list_requests(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    requests, total = request_service.get_all_requests(db, skip=skip, limit=limit)
    items = []
    for r, candidate_count in requests:
        items.append(
            RecruitmentRequestListItem(
                id=r.id,
                title=r.title,
                status=r.status,
                candidate_count=candidate_count,
                platforms=r.platforms,
                created_at=r.created_at,
            )
        )
    return RecruitmentRequestListResponse(items=items, total=total)


@router.get("/{request_id}", response_model=RecruitmentRequestResponse)
def get_request(request_id: int, db: Session = Depends(get_db)):
    req = request_service.get_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return _to_response(req)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: int, db: Session = Depends(get_db)):
    deleted = request_service.delete_request(db, request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Request not found")


def _to_response(req) -> RecruitmentRequestResponse:
    return RecruitmentRequestResponse(
        id=req.id,
        title=req.title,
        required_skills=req.required_skills,
        experience_min=req.experience_min,
        experience_max=req.experience_max,
        location=req.location,
        keywords=req.keywords,
        platforms=req.platforms,
        status=req.status,
        candidate_count=len(req.candidates),
        scrape_jobs=[
            ScrapeJobSummary(
                id=j.id,
                platform=j.platform,
                status=j.status,
                candidates_found=j.candidates_found,
                started_at=j.started_at,
                completed_at=j.completed_at,
            )
            for j in req.scrape_jobs
        ],
        created_at=req.created_at,
        updated_at=req.updated_at,
    )
