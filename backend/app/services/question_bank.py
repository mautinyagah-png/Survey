import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.question_bank import (
    QuestionBankOption,
    QuestionBankQuestion,
    QuestionBankTitle,
)
from app.models.surveys import AnswerOption, Survey, SurveyQuestion
from app.schemas.question_bank import (
    BankQuestionCreate,
    BankQuestionUpdate,
    BankTitleCreate,
    BankTitleUpdate,
)

CHOICE_TYPES = {"single_choice", "multi_select", "dropdown"}


def make_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "question-title"


def unique_slug(db: Session, title: str, supplied: str | None = None) -> str:
    base = make_slug(supplied or title)
    slug = base
    number = 2

    while db.scalar(
        select(QuestionBankTitle.id).where(QuestionBankTitle.slug == slug)
    ):
        slug = f"{base}-{number}"
        number += 1

    return slug


def title_output(db: Session, title: QuestionBankTitle) -> dict:
    count = db.scalar(
        select(func.count(QuestionBankQuestion.id)).where(
            QuestionBankQuestion.title_id == title.id
        )
    )
    return {
        "id": title.id,
        "title": title.title,
        "slug": title.slug,
        "description": title.description,
        "sort_order": title.sort_order,
        "is_active": title.is_active,
        "access_tier": title.access_tier,
        "question_count": count or 0,
    }


def question_output(db: Session, question: QuestionBankQuestion) -> dict:
    options = db.scalars(
        select(QuestionBankOption)
        .where(QuestionBankOption.question_id == question.id)
        .order_by(QuestionBankOption.order_index)
    ).all()

    return {
        "id": question.id,
        "title_id": question.title_id,
        "order_index": question.order_index,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "help_text": question.help_text,
        "is_required": question.is_required,
        "config": question.config,
        "options": options,
    }


def survey_question_output(db: Session, question: SurveyQuestion) -> dict:
    options = db.scalars(
        select(AnswerOption)
        .where(AnswerOption.question_id == question.id)
        .order_by(AnswerOption.order_index)
    ).all()

    return {
        "id": question.id,
        "order_index": question.order_index,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "help_text": question.help_text,
        "is_required": question.is_required,
        "config": question.config,
        "options": [
            {
                "id": option.id,
                "order_index": option.order_index,
                "label": option.label,
                "value": option.value,
            }
            for option in options
        ],
    }


def list_titles(db: Session, active_only: bool = False) -> list[dict]:
    query = select(QuestionBankTitle).order_by(
        QuestionBankTitle.sort_order, QuestionBankTitle.title
    )
    if active_only:
        query = query.where(QuestionBankTitle.is_active.is_(True))
    return [title_output(db, item) for item in db.scalars(query).all()]


def create_title(db: Session, data: BankTitleCreate) -> dict:
    title = QuestionBankTitle(
        title=data.title.strip(),
        slug=unique_slug(db, data.title, data.slug),
        description=data.description,
        sort_order=data.sort_order,
        access_tier=data.access_tier,
    )
    db.add(title)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A title with that slug already exists.")
    db.refresh(title)
    return title_output(db, title)


def update_title(
    db: Session, title_id: UUID, data: BankTitleUpdate
) -> dict:
    title = db.get(QuestionBankTitle, title_id)
    if title is None:
        raise ValueError("Question Bank title not found.")

    values = data.model_dump(exclude_unset=True)

    for field in ("title", "sort_order", "is_active"):
        if field in values and values[field] is None:
            raise ValueError(f"{field} cannot be null.")

    for field, value in values.items():
        if field == "title":
            value = value.strip()
            if not value:
                raise ValueError("Title cannot be empty.")
        setattr(title, field, value)

    title.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(title)
    return title_output(db, title)


def require_title(db: Session, title_id: UUID) -> QuestionBankTitle:
    title = db.get(QuestionBankTitle, title_id)
    if title is None:
        raise ValueError("Question Bank title not found.")
    if not title.is_active:
        raise ValueError("This Question Bank title is inactive.")
    return title


def list_bank_questions(db: Session, title_id: UUID) -> list[dict]:
    if db.get(QuestionBankTitle, title_id) is None:
        raise ValueError("Question Bank title not found.")

    questions = db.scalars(
        select(QuestionBankQuestion)
        .where(QuestionBankQuestion.title_id == title_id)
        .order_by(QuestionBankQuestion.order_index)
    ).all()
    return [question_output(db, item) for item in questions]


def create_bank_question(
    db: Session, title_id: UUID, data: BankQuestionCreate
) -> dict:
    require_title(db, title_id)

    if data.question_type in CHOICE_TYPES and len(data.options) < 2:
        raise ValueError("Choice questions require at least two answer options.")
    if data.question_type not in CHOICE_TYPES and data.options:
        raise ValueError("This question type does not accept answer options.")

    if data.order_index is None:
        maximum = db.scalar(
            select(func.max(QuestionBankQuestion.order_index)).where(
                QuestionBankQuestion.title_id == title_id
            )
        )
        order_index = (maximum if maximum is not None else -1) + 1
    else:
        order_index = data.order_index

    question = QuestionBankQuestion(
        title_id=title_id,
        order_index=order_index,
        question_type=data.question_type,
        prompt=data.prompt,
        help_text=data.help_text,
        is_required=data.is_required,
        config=data.config,
    )
    db.add(question)
    try:
        db.flush()
        for index, option in enumerate(data.options):
            db.add(QuestionBankOption(
                question_id=question.id,
                order_index=index,
                label=option.label,
                value=option.value,
            ))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("That question order is already in use.")

    db.refresh(question)
    return question_output(db, question)


def update_bank_question(
    db: Session, question_id: UUID, data: BankQuestionUpdate
) -> dict:
    question = db.get(QuestionBankQuestion, question_id)
    if question is None:
        raise ValueError("Question Bank question not found.")
    require_title(db, question.title_id)

    values = data.model_dump(exclude_unset=True)
    options = values.pop("options", None)
    new_type = values.get("question_type") or question.question_type

    if any(
        key in values and values[key] is None
        for key in ("question_type", "prompt", "is_required", "order_index", "config")
    ):
        raise ValueError("Required question fields cannot be null.")

    if "prompt" in values:
        values["prompt"] = values["prompt"].strip()
        if not values["prompt"]:
            raise ValueError("Question cannot be empty.")

    existing_options = db.scalars(
        select(QuestionBankOption).where(
            QuestionBankOption.question_id == question.id
        )
    ).all()

    if options is not None:
        if new_type in CHOICE_TYPES and len(options) < 2:
            raise ValueError("Choice questions require at least two answer options.")
        if new_type not in CHOICE_TYPES and options:
            raise ValueError("This question type does not accept answer options.")
    elif new_type in CHOICE_TYPES and question.question_type not in CHOICE_TYPES:
        raise ValueError("Provide at least two answer options for this question type.")
    elif new_type in CHOICE_TYPES and len(existing_options) < 2:
        raise ValueError("Provide at least two answer options for this question type.")

    for field, value in values.items():
        setattr(question, field, value)

    if options is not None or new_type not in CHOICE_TYPES:
        db.query(QuestionBankOption).filter(
            QuestionBankOption.question_id == question.id
        ).delete(synchronize_session=False)

        if options:
            for index, option in enumerate(options):
                db.add(QuestionBankOption(
                    question_id=question.id,
                    order_index=index,
                    label=option["label"],
                    value=option["value"],
                ))

    question.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("That question order is already in use.")

    db.refresh(question)
    return question_output(db, question)


def delete_bank_question(db: Session, question_id: UUID) -> None:
    question = db.get(QuestionBankQuestion, question_id)
    if question is None:
        raise ValueError("Question Bank question not found.")
    require_title(db, question.title_id)
    db.delete(question)
    db.commit()


def copy_bank_question_to_survey(
    db: Session,
    survey_id: UUID,
    bank_question_id: UUID,
) -> dict:
    survey = db.get(Survey, survey_id)
    if survey is None or survey.deleted_at is not None:
        raise ValueError("Survey not found.")
    if survey.status != "draft":
        raise ValueError("Questions can only be added while a survey is a draft.")

    bank_question = db.get(QuestionBankQuestion, bank_question_id)
    if bank_question is None:
        raise ValueError("Question Bank question not found.")
    require_title(db, bank_question.title_id)

    maximum = db.scalar(
        select(func.max(SurveyQuestion.order_index)).where(
            SurveyQuestion.survey_id == survey_id
        )
    )
    question = SurveyQuestion(
        survey_id=survey_id,
        order_index=(maximum if maximum is not None else -1) + 1,
        question_type=bank_question.question_type,
        prompt=bank_question.prompt,
        help_text=bank_question.help_text,
        is_required=bank_question.is_required,
        config=bank_question.config,
    )
    db.add(question)
    db.flush()

    options = db.scalars(
        select(QuestionBankOption)
        .where(QuestionBankOption.question_id == bank_question.id)
        .order_by(QuestionBankOption.order_index)
    ).all()

    for option in options:
        db.add(AnswerOption(
            question_id=question.id,
            order_index=option.order_index,
            label=option.label,
            value=option.value,
        ))

    db.commit()
    db.refresh(question)

    survey_options = db.scalars(
        select(AnswerOption)
        .where(AnswerOption.question_id == question.id)
        .order_by(AnswerOption.order_index)
    ).all()

    return {
        "id": question.id,
        "survey_id": question.survey_id,
        "order_index": question.order_index,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "help_text": question.help_text,
        "is_required": question.is_required,
        "config": question.config,
        "options": survey_options,
    }


def generate_survey_questions_from_bank(
    db: Session,
    survey_id: UUID,
    title_ids: list[UUID],
    question_count: int = 10,
    shuffle: bool = True,
) -> dict:
    import random

    survey = db.get(Survey, survey_id)
    if survey is None or survey.deleted_at is not None:
        raise ValueError("Survey not found.")
    if survey.status != "draft":
        raise ValueError("Questions can only be generated for draft surveys.")

    selected_ids = list(dict.fromkeys(title_ids))
    titles = db.scalars(
        select(QuestionBankTitle).where(
            QuestionBankTitle.id.in_(selected_ids),
            QuestionBankTitle.is_active.is_(True),
        )
    ).all()

    if len(titles) != len(selected_ids):
        raise ValueError("One or more selected question bank categories are unavailable.")

    bank_questions = db.scalars(
        select(QuestionBankQuestion)
        .where(QuestionBankQuestion.title_id.in_(selected_ids))
        .order_by(
            QuestionBankQuestion.title_id,
            QuestionBankQuestion.order_index,
        )
    ).all()

    existing_prompts = {
        prompt.strip().casefold()
        for prompt in db.scalars(
            select(SurveyQuestion.prompt).where(
                SurveyQuestion.survey_id == survey_id
            )
        ).all()
    }

    candidates = [
        question for question in bank_questions
        if question.prompt.strip().casefold() not in existing_prompts
    ]

    if shuffle:
        random.shuffle(candidates)

    if len(candidates) < question_count:
        raise ValueError(
            f"Only {len(candidates)} unused questions are available "
            f"in the selected categories; {question_count} requested."
        )

    chosen = candidates[:question_count]

    maximum = db.scalar(
        select(func.max(SurveyQuestion.order_index)).where(
            SurveyQuestion.survey_id == survey_id
        )
    )
    next_order = (maximum if maximum is not None else -1) + 1
    created = []

    try:
        for bank_question in chosen:
            question = SurveyQuestion(
                survey_id=survey_id,
                order_index=next_order,
                question_type=bank_question.question_type,
                prompt=bank_question.prompt,
                help_text=bank_question.help_text,
                is_required=bank_question.is_required,
                config=bank_question.config,
            )
            db.add(question)
            db.flush()

            bank_options = db.scalars(
                select(QuestionBankOption)
                .where(
                    QuestionBankOption.question_id == bank_question.id
                )
                .order_by(QuestionBankOption.order_index)
            ).all()

            for index, option in enumerate(bank_options):
                db.add(AnswerOption(
                    question_id=question.id,
                    order_index=index,
                    label=option.label,
                    value=option.value,
                ))

            created.append(question)
            next_order += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    for question in created:
        db.refresh(question)

    return {
        "created_count": len(created),
        "survey_id": survey_id,
        "questions": [
            survey_question_output(db, question) for question in created
        ],
    }
