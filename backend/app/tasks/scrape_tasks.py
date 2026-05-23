"""
Celery tasks for async candidate scraping and ranking.

Flow:
  run_recruitment_scrape(request_id)
    └─ for each platform → scrape_platform(scrape_job_id)   [parallel group]
         └─ chord callback → rank_and_complete(request_id)
"""

import asyncio
from datetime import datetime, timezone

from celery import group, chord
from sqlalchemy.exc import IntegrityError

from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.models.recruitment_request import RecruitmentRequest
from app.models.scrape_job import ScrapeJob
from app.models.candidate import Candidate
from app.connectors import get_connector, RecruitmentCriteria
from app.services import ranking_service
from app.utils.text_utils import parse_skills_from_headline, parse_experience_from_headline
from app.services.ai_service import generate_search_queries
from app.services.email_service import find_email
from app.services.email_sender import send_outreach_email


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Orchestrator ──────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.run_recruitment_scrape")
def run_recruitment_scrape(self, request_id: int):
    """
    Entry-point task. Sets request to 'running', dispatches one
    scrape_platform subtask per platform, then waits for the chord callback.
    """
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter_by(id=request_id).first()
        if not req:
            return

        req.status = "running"
        db.commit()

        scrape_jobs = req.scrape_jobs
        if not scrape_jobs:
            req.status = "failed"
            db.commit()
            return

        # Build a chord: parallel scrape tasks → ranking callback
        job_ids = [job.id for job in scrape_jobs]
        scrape_group = group(scrape_platform.s(job_id) for job_id in job_ids)
        callback = rank_and_complete.s(request_id)
        chord(scrape_group)(callback)

    finally:
        db.close()


# ── Per-platform scraper ──────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.scrape_platform",
    max_retries=2,
    default_retry_delay=60,
)
def scrape_platform(self, scrape_job_id: int):
    """
    Scrapes one platform for a given scrape_job.
    Inserts candidates into DB (dedup-safe).
    Returns the number of candidates found.
    """
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter_by(id=scrape_job_id).first()
        if not job:
            return 0

        job.status = "running"
        job.started_at = _now()
        db.commit()

        req = job.request

        # Normalize skills/keywords: handle both list-of-strings and single comma-separated string
        def _split(val):
            if not val:
                return []
            if isinstance(val, str):
                return [s.strip() for s in val.split(",") if s.strip()]
            # list — each item may itself be comma-separated
            result = []
            for item in val:
                result.extend(s.strip() for s in str(item).split(",") if s.strip())
            return result

        skills = _split(req.required_skills)
        keywords = _split(req.keywords)

        search_queries = generate_search_queries(
            title=req.title,
            skills=skills,
            keywords=keywords,
            location=req.location,
            experience_min=req.experience_min or 0,
            experience_max=req.experience_max,
        )

        criteria = RecruitmentCriteria(
            title=req.title,
            required_skills=skills,
            experience_min=req.experience_min,
            experience_max=req.experience_max,
            location=req.location,
            keywords=keywords,
            max_results=50,
            search_queries=search_queries,
        )

        # Run async connector in a sync Celery task
        connector = get_connector(job.platform)
        raw_candidates = asyncio.run(connector.search(criteria))

        def _trunc(val, n):
            return val[:n] if isinstance(val, str) else val

        inserted = 0
        for raw in raw_candidates:
            # Fill missing skills + experience from headline for card-only candidates
            skills = raw.skills or parse_skills_from_headline(raw.headline or "")
            exp_years = raw.experience_years
            if exp_years is None:
                exp_years = parse_experience_from_headline(raw.headline or "")

            candidate = Candidate(
                request_id=req.id,
                scrape_job_id=job.id,
                platform=raw.platform,
                platform_id=_trunc(raw.platform_id, 255),
                full_name=_trunc(raw.full_name, 255),
                headline=_trunc(raw.headline, 500),
                location=_trunc(raw.location, 255),
                experience_years=exp_years,
                skills=skills,
                profile_url=_trunc(raw.profile_url, 1000),
                summary=raw.summary,
                raw_data=raw.raw_data,
            )
            try:
                db.add(candidate)
                db.flush()
                inserted += 1
            except IntegrityError:
                db.rollback()  # duplicate — skip silently

        db.commit()

        job.status = "completed"
        job.candidates_found = inserted
        job.completed_at = _now()
        db.commit()

        return inserted

    except Exception as exc:
        db.rollback()
        job = db.query(ScrapeJob).filter_by(id=scrape_job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = _now()
            db.commit()
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0
    finally:
        db.close()


# ── Chord callback — ranking ──────────────────────────────────────────────────

@celery_app.task(name="tasks.rank_and_complete")
def rank_and_complete(platform_results: list[int], request_id: int):
    """
    Chord callback: fires after ALL scrape_platform tasks finish.
    Scores + ranks all candidates, then marks the request completed.
    """
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter_by(id=request_id).first()
        if not req:
            return

        candidates = (
            db.query(Candidate)
            .filter(Candidate.request_id == request_id)
            .all()
        )

        if candidates:
            ranking_service.score_and_rank(candidates, req)
            db.commit()

        # Check if any scrape job succeeded
        jobs = req.scrape_jobs
        all_failed = all(j.status == "failed" for j in jobs)
        req.status = "failed" if all_failed else "completed"
        db.commit()

        # Fire background email enrichment for top 10 candidates
        if not all_failed:
            enrich_emails.delay(request_id)

    finally:
        db.close()


# ── Email enrichment ──────────────────────────────────────────────────────────

def _backfill_linkedin_profile(db, candidate: Candidate) -> None:
    """
    Visit a LinkedIn profile page to fill in missing skills, experience, location,
    and email (from Contact Info modal) for a candidate that was not enriched
    during the initial search scrape.
    """
    if not candidate.profile_url:
        return
    try:
        from app.connectors.linkedin import LinkedInConnector
        conn = LinkedInConnector()
        raw = asyncio.run(conn.enrich_single_profile(candidate.profile_url))
        if not raw:
            return

        updated = []
        if raw.skills and not candidate.skills:
            candidate.skills = raw.skills
            updated.append(f"skills={len(raw.skills)}")
        if raw.experience_years is not None and candidate.experience_years is None:
            candidate.experience_years = raw.experience_years
            updated.append(f"exp={raw.experience_years}yrs")
        if raw.location and not candidate.location:
            candidate.location = raw.location
            updated.append("location")
        if raw.summary and not candidate.summary:
            candidate.summary = raw.summary
        if raw.full_name and not candidate.full_name:
            candidate.full_name = raw.full_name
        if raw.headline and not candidate.headline:
            candidate.headline = raw.headline

        # Store Contact Info email in raw_data so find_email() picks it up
        contact_email = (raw.raw_data or {}).get("email")
        if contact_email:
            raw_data = dict(candidate.raw_data or {})
            raw_data["email"] = contact_email
            candidate.raw_data = raw_data
            updated.append("email")

        db.commit()
        if updated:
            print(f"[Enrich] #{candidate.rank} {candidate.full_name}: backfilled {', '.join(updated)}")

    except Exception as e:
        print(f"[Enrich] Profile backfill failed for {candidate.full_name}: {e}")


@celery_app.task(name="tasks.enrich_emails")
def enrich_emails(request_id: int):
    """
    Background task — three phases:
      Phase 1: Backfill LinkedIn profile data (skills/exp/location/email) for
               top-10 candidates that were not visited during the search scrape.
      Phase 2: Re-rank ALL candidates now that profile data is complete, so
               scores reflect actual skills/experience rather than headline guesses.
      Phase 3: Find emails + send outreach for the (updated) top 10.
    """
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter_by(id=request_id).first()
        if not req:
            return

        skills_list = req.required_skills if isinstance(req.required_skills, list) else []

        # ── Phase 1: backfill profiles ────────────────────────────────────────
        top10 = (
            db.query(Candidate)
            .filter(Candidate.request_id == request_id)
            .filter(Candidate.rank <= 10)
            .order_by(Candidate.rank)
            .all()
        )

        backfilled = 0
        for candidate in top10:
            needs_backfill = (
                candidate.platform == "linkedin"
                and candidate.profile_url
                and (not candidate.skills or candidate.experience_years is None)
            )
            if needs_backfill:
                print(f"[Enrich] #{candidate.rank} {candidate.full_name}: visiting profile…")
                _backfill_linkedin_profile(db, candidate)
                backfilled += 1

        # ── Phase 2: re-rank with complete data ───────────────────────────────
        if backfilled > 0:
            all_candidates = (
                db.query(Candidate)
                .filter(Candidate.request_id == request_id)
                .all()
            )
            ranking_service.score_and_rank(all_candidates, req)
            db.commit()
            print(f"[Enrich] Re-ranked {len(all_candidates)} candidates after backfilling {backfilled} profiles")

        # ── Phase 3: email + outreach for (updated) top 10 ───────────────────
        top10 = (
            db.query(Candidate)
            .filter(Candidate.request_id == request_id)
            .filter(Candidate.rank <= 10)
            .order_by(Candidate.rank)
            .all()
        )

        for candidate in top10:
            try:
                email, status = find_email(candidate)
                candidate.email = email
                candidate.email_status = status
                db.commit()
                print(f"[Email] #{candidate.rank} {candidate.full_name}: {email or status}")

                if email and status in ("found", "guessed"):
                    sent = send_outreach_email(
                        to_email=email,
                        candidate_name=candidate.full_name or "",
                        job_title=req.title,
                        skills=skills_list[:2],
                    )
                    candidate.email_sent = sent
                    db.commit()

            except Exception as e:
                print(f"[Email] Failed for candidate {candidate.id}: {e}")

    finally:
        db.close()


