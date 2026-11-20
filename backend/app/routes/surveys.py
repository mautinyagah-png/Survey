"""Public and administrator survey endpoints."""

from datetime import datetime, timezone

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.models.surveys import Survey
from app.schemas.surveys import (
    SurveyCatalogueItem,
    SurveyCreate,
    SurveyListResponse,
    SurveyPublic,
    SurveyUpdate,
)
from app.security.dependencies import get_admin_user, get_optional_current_user
from app.services.surveys import (
    change_survey_status,
    create_survey,
    get_public_surveys,
    update_survey,
)

from app.services.subscriptions import can_access_tier, get_effective_subscription

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def get_survey_or_404(db: Session, survey_id: UUID) -> Survey:
    survey = db.scalar(
        select(Survey).where(
            Survey.id == survey_id,
            Survey.deleted_at.is_(None),
        )
    )
    if survey is None:
        raise HTTPException(status_code=404, detail="Survey not found.")
    return survey


@router.get("/", response_model=SurveyListResponse)
def list_surveys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    category_id: UUID | None = None,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    items, total = get_public_surveys(
        db, page, page_size, country_code, category_id
    )

    tier_rank = (
        get_effective_subscription(db, user.id)["tier_rank"]
        if user is not None else 1
    )

    catalogue = [
        SurveyCatalogueItem(
            id=item.id,
            title=item.title,
            required_tier=item.required_tier,
            is_locked=not can_access_tier(tier_rank, item.required_tier),
            category_id=item.category_id,
            estimated_minutes=item.estimated_minutes,
            reward_amount=item.reward_amount,
            reward_currency=item.reward_currency,
        )
        for item in items
    ]

    return {
        "items": catalogue,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/admin/all", response_model=list[SurveyPublic])
def admin_list_surveys(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    survey_status: str | None = Query(
        default=None,
        pattern=r"^(draft|published|closed|archived)$",
    ),
):
    query = select(Survey).where(Survey.deleted_at.is_(None))
    if survey_status:
        query = query.where(Survey.status == survey_status)
    return db.scalars(query.order_by(Survey.created_at.desc())).all()



@router.get("/{survey_id}", response_model=SurveyPublic)
def get_survey(
    survey_id: UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    survey = get_survey_or_404(db, survey_id)
    now = datetime.now(timezone.utc)

    if (
        survey.status != "published"
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
                    "to participate in this survey."
                ),
            },
        )

    return survey


@router.post(
    "/",
    response_model=SurveyPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_survey_route(
    data: SurveyCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return create_survey(db, data, admin.id)


@router.patch("/{survey_id}", response_model=SurveyPublic)
def update_survey_route(
    survey_id: UUID,
    data: SurveyUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    survey = get_survey_or_404(db, survey_id)

    if survey.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only draft surveys can be edited.",
        )

    try:
        return update_survey(db, survey, data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{survey_id}/publish", response_model=SurveyPublic)
def publish_survey(
    survey_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    survey = get_survey_or_404(db, survey_id)
    try:
        return change_survey_status(db, survey, "published")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{survey_id}/close", response_model=SurveyPublic)
def close_survey(
    survey_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    survey = get_survey_or_404(db, survey_id)
    try:
        return change_survey_status(db, survey, "closed")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{survey_id}/archive", response_model=SurveyPublic)
def archive_survey(
    survey_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    survey = get_survey_or_404(db, survey_id)
    try:
        return change_survey_status(db, survey, "archived")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
