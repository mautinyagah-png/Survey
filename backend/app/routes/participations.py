"""Respondent survey participation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.models.participations import Participation
from app.models.surveys import Survey
from sqlalchemy import func, select
from app.schemas.participations import (
    ParticipationPublic,
    ParticipationHistoryItem,
    ParticipationHistoryResponse,
    ParticipationSubmitResult,
    ResponseBatch,
    QuestionViewResult,
    ResponseSaveResult,
    ResponsePublic,
)
from app.security.dependencies import get_current_user
from app.services.participations import (
    ParticipationError,
    record_question_view,
    save_responses,
    start_participation,
    submit_participation,
)

router = APIRouter(tags=["participations"])


def handle_error(exc: ParticipationError):
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.message,
    ) from exc


@router.post(
    "/api/surveys/{survey_id}/participations",
    response_model=ParticipationPublic,
    status_code=status.HTTP_201_CREATED,
)
def start_survey_participation(
    survey_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return start_participation(db, user, survey_id)
    except ParticipationError as exc:
        handle_error(exc)


@router.post(
    "/api/participations/{participation_id}/questions/{question_id}/view",
    response_model=QuestionViewResult,
)
def mark_question_viewed(
    participation_id: UUID,
    question_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return record_question_view(db, user, participation_id, question_id)
    except ParticipationError as exc:
        handle_error(exc)


@router.get(
    "/api/participations/{participation_id}/responses",
    response_model=list[ResponsePublic],
)
def get_participation_responses(
    participation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return saved answers so the frontend can resume at the right question."""
    from app.models.participations import Participation, Response
    from sqlalchemy import select as _sel

    participation = db.scalar(
        _sel(Participation).where(
            Participation.id == participation_id,
            Participation.user_id == user.id,
        )
    )
    if participation is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Participation not found.")

    return db.scalars(
        _sel(Response).where(Response.participation_id == participation.id)
    ).all()


@router.put(
    "/api/participations/{participation_id}/responses",
    response_model=ResponseSaveResult,
)
def save_survey_responses(
    participation_id: UUID,
    data: ResponseBatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return save_responses(
            db, user, participation_id, data.answers
        )
    except ParticipationError as exc:
        handle_error(exc)


@router.post(
    "/api/participations/{participation_id}/submit",
    response_model=ParticipationSubmitResult,
)
def submit_survey_participation(
    participation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        participation = submit_participation(
            db, user, participation_id
        )
        return {
            "participation_id": participation.id,
            "status": participation.status,
            "submitted_at": participation.submitted_at,
        }
    except ParticipationError as exc:
        handle_error(exc)


@router.get(
    "/api/participations/me",
    response_model=ParticipationHistoryResponse,
)
def get_my_participations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return only the authenticated respondent's participation history."""

    filters = [Participation.user_id == user.id]

    total = db.scalar(
        select(func.count(Participation.id)).where(*filters)
    ) or 0

    rows = db.execute(
        select(
            Participation,
            Survey.title,
            Survey.reward_amount,
            Survey.reward_currency,
        )
        .join(Survey, Survey.id == Participation.survey_id)
        .where(*filters)
        .order_by(Participation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        ParticipationHistoryItem(
            id=participation.id,
            survey_id=participation.survey_id,
            survey_title=title,
            reward_amount=float(reward_amount),
            reward_currency=currency,
            status=participation.status,
            started_at=participation.started_at,
            submitted_at=participation.submitted_at,
            reviewed_at=participation.reviewed_at,
        )
        for participation, title, reward_amount, currency in rows
    ]

    return ParticipationHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
