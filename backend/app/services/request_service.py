from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.recruitment_request import RecruitmentRequest
from app.models.scrape_job import ScrapeJob
from app.models.candidate import Candidate
from app.schemas.recruitment_request import RecruitmentRequestCreate


def create_request(db: Session, data: RecruitmentRequestCreate) -> RecruitmentRequest:
    req = RecruitmentRequest(
        title=data.title,
        required_skills=data.required_skills,
        experience_min=data.experience_min,
        experience_max=data.experience_max,
        location=data.location,
        keywords=data.keywords,
        platforms=data.platforms,
        status="pending",
    )
    db.add(req)
    db.flush()

    for platform in data.platforms:
        job = ScrapeJob(request_id=req.id, platform=platform, status="pending")
        db.add(job)

    db.commit()
    db.refresh(req)
    return req


def get_request(db: Session, request_id: int) -> RecruitmentRequest | None:
    return db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()


def get_all_requests(db: Session, skip: int = 0, limit: int = 100):
    # Single query: requests + candidate counts via subquery (no N+1)
    count_subq = (
        db.query(Candidate.request_id, func.count(Candidate.id).label("cnt"))
        .group_by(Candidate.request_id)
        .subquery()
    )
    rows = (
        db.query(RecruitmentRequest, func.coalesce(count_subq.c.cnt, 0).label("candidate_count"))
        .outerjoin(count_subq, RecruitmentRequest.id == count_subq.c.request_id)
        .order_by(RecruitmentRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(func.count(RecruitmentRequest.id)).scalar()
    return rows, total


def delete_request(db: Session, request_id: int) -> bool:
    req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
    if not req:
        return False
    db.delete(req)
    db.commit()
    return True


def get_candidates(
    db: Session,
    request_id: int,
    platform: str | None = None,
    min_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(Candidate).filter(Candidate.request_id == request_id)
    if platform:
        query = query.filter(Candidate.platform == platform)
    if min_score is not None:
        query = query.filter(Candidate.suitability_score >= min_score)
    total = query.count()
    items = query.order_by(Candidate.rank.asc()).offset(offset).limit(limit).all()
    return items, total
