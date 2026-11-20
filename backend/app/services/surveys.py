"""Business logic for survey management."""

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.surveys import AnswerOption, Survey, SurveyCategory, SurveyQuestion
from app.schemas.surveys import SurveyCreate, SurveyUpdate


def make_unique_slug(
    db: Session, title: str, supplied: str | None = None,
    exclude_id: UUID | None = None,
) -> str:
    source = supplied or title
    base = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    base = base[:200].strip("-") or "survey"
    candidate = base
    number = 2

    while db.scalar(
        select(Survey.id).where(
            Survey.slug == candidate,
            Survey.id != exclude_id if exclude_id else True,
        )
    ):
        suffix = f"-{number}"
        candidate = base[:220 - len(suffix)] + suffix
        number += 1

    return candidate


def create_survey(db: Session, data: SurveyCreate, user_id: UUID) -> Survey:
    values = data.model_dump()
    supplied_slug = values.pop("slug")
    values["slug"] = make_unique_slug(db, values["title"], supplied_slug)
    values["created_by"] = user_id

    survey = Survey(**values)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


def update_survey(
    db: Session,
    survey: Survey,
    data: SurveyUpdate,
) -> Survey:
    values = data.model_dump(exclude_unset=True)

    if "title" in values and values["title"] is None:
        raise ValueError("Survey title cannot be empty.")

    if values.get("category_id") is not None:
        if db.get(SurveyCategory, values["category_id"]) is None:
            raise ValueError("The selected survey category does not exist.")

    if values.get("slug") is not None:
        if values["slug"] == survey.slug:
            values.pop("slug")
        else:
            values["slug"] = make_unique_slug(
                db, values.get("title", survey.title),
                values["slug"], exclude_id=survey.id,
            )
    elif "slug" in values:
        values.pop("slug")

    for field, value in values.items():
        setattr(survey, field, value)

    db.commit()
    db.refresh(survey)
    return survey


def change_survey_status(
    db: Session,
    survey: Survey,
    new_status: str,
) -> Survey:
    now = datetime.now(timezone.utc)

    if new_status == "published":
        if survey.status not in {"draft", "closed"}:
            raise ValueError("Only draft or closed surveys can be published.")
        if survey.closes_at is not None and survey.closes_at <= now:
            raise ValueError("The closing date must be in the future.")

        questions = db.scalars(
            select(SurveyQuestion).where(
                SurveyQuestion.survey_id == survey.id
            )
        ).all()

        if not questions:
            raise ValueError("Add at least one question before publishing.")

        choice_types = {"single_choice", "multi_select", "dropdown"}

        for question in questions:
            if question.question_type in choice_types:
                option_count = db.scalar(
                    select(func.count()).select_from(AnswerOption).where(
                        AnswerOption.question_id == question.id
                    )
                ) or 0

                if option_count < 2:
                    raise ValueError(
                        "Each choice or dropdown question needs at least two answer options."
                    )

        survey.published_at = now

    elif new_status == "closed":
        if survey.status != "published":
            raise ValueError("Only published surveys can be closed.")

    elif new_status == "archived":
        if survey.status == "archived":
            raise ValueError("Survey is already archived.")
        if survey.status == "published":
            raise ValueError("Close the published survey before archiving it.")

    survey.status = new_status
    db.commit()
    db.refresh(survey)
    return survey


def get_public_surveys(
    db: Session,
    page: int,
    page_size: int,
    country_code: str | None = None,
    category_id: UUID | None = None,
):
    now = datetime.now(timezone.utc)

    filters = [
        Survey.status == "published",
        Survey.deleted_at.is_(None),
        (Survey.closes_at.is_(None) | (Survey.closes_at > now)),
        (
            Survey.participant_target.is_(None)
            | (Survey.participant_count < Survey.participant_target)
        ),
    ]

    if country_code:
        filters.append(
            (Survey.country_code.is_(None))
            | (Survey.country_code == country_code.upper())
        )

    if category_id:
        filters.append(Survey.category_id == category_id)

    total = db.scalar(
        select(func.count()).select_from(Survey).where(*filters)
    ) or 0

    items = db.scalars(
        select(Survey)
        .where(*filters)
        .order_by(Survey.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return items, total
