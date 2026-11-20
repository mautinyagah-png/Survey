from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.schemas.questions import QuestionCreate, QuestionPublic, QuestionUpdate
from app.security.dependencies import get_admin_user, get_optional_current_user
from app.services.subscriptions import can_access_tier, get_effective_subscription
from app.models.surveys import Survey
from app.services.questions import (
    create_question,
    delete_question,
    list_public_questions,
    list_questions,
    update_question,
)

router = APIRouter(tags=["survey-questions"])


@router.get(
    "/api/admin/surveys/{survey_id}/questions",
    response_model=list[QuestionPublic],
)
def admin_list_questions(
    survey_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.models.surveys import Survey

    survey = db.get(Survey, survey_id)
    if survey is None or survey.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Survey not found.")

    return list_questions(db, survey_id)


@router.post(
    "/api/admin/surveys/{survey_id}/questions",
    response_model=QuestionPublic,
    status_code=status.HTTP_201_CREATED,
)
def add_question(
    survey_id: UUID,
    data: QuestionCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return create_question(db, survey_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/api/admin/questions/{question_id}",
    response_model=QuestionPublic,
)
def edit_question(
    question_id: UUID,
    data: QuestionUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return update_question(db, question_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/api/admin/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_question(
    question_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        delete_question(db, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/api/surveys/{survey_id}/questions",
    response_model=list[QuestionPublic],
)
def public_list_questions(
    survey_id: UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    survey = db.get(Survey, survey_id)
    now = datetime.now(timezone.utc)

    if (
        survey is None
        or survey.deleted_at is not None
        or survey.status != "published"
        or (survey.closes_at is not None and survey.closes_at <= now)
        or (
            survey.participant_target is not None
            and survey.participant_count >= survey.participant_target
        )
    ):
        raise HTTPException(status_code=404, detail="Survey not found.")

    tier_rank = (
        get_effective_subscription(db, user.id)["tier_rank"]
        if user is not None else 1
    )

    if not can_access_tier(tier_rank, survey.required_tier):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "upgrade_required",
                "required_tier": survey.required_tier,
                "message": (
                    f"Upgrade to {survey.required_tier.title()} "
                    "to view this survey's questions."
                ),
            },
        )

    try:
        return list_public_questions(db, survey_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
