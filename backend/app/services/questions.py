from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.surveys import AnswerOption, Survey, SurveyQuestion
from app.schemas.questions import QuestionCreate, QuestionUpdate


CHOICE_TYPES = {"single_choice", "multi_select", "dropdown"}


def require_draft_survey(db: Session, survey_id: UUID) -> Survey:
    survey = db.get(Survey, survey_id)

    if survey is None or survey.deleted_at is not None:
        raise ValueError("Survey not found.")

    if survey.status != "draft":
        raise ValueError("Questions can only be changed while a survey is a draft.")

    return survey


def question_output(db: Session, question: SurveyQuestion) -> dict:
    options = db.scalars(
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
        "options": options,
    }


def list_questions(db: Session, survey_id: UUID) -> list[dict]:
    questions = db.scalars(
        select(SurveyQuestion)
        .where(SurveyQuestion.survey_id == survey_id)
        .order_by(SurveyQuestion.order_index)
    ).all()

    return [question_output(db, q) for q in questions]


def create_question(
    db: Session, survey_id: UUID, data: QuestionCreate
) -> dict:
    require_draft_survey(db, survey_id)

    if data.question_type in CHOICE_TYPES and len(data.options) < 2:
        raise ValueError("Choice questions require at least two answer options.")

    if data.question_type not in CHOICE_TYPES and data.options:
        raise ValueError("This question type does not accept answer options.")

    if data.order_index is None:
        current_max = db.scalar(
            select(func.max(SurveyQuestion.order_index))
            .where(SurveyQuestion.survey_id == survey_id)
        )
        order_index = (current_max if current_max is not None else -1) + 1
    else:
        order_index = data.order_index

    question = SurveyQuestion(
        survey_id=survey_id,
        order_index=order_index,
        question_type=data.question_type,
        prompt=data.prompt,
        help_text=data.help_text,
        is_required=data.is_required,
        config=data.config,
    )
    db.add(question)
    db.flush()

    for index, option in enumerate(data.options):
        db.add(AnswerOption(
            question_id=question.id,
            order_index=index,
            label=option.label,
            value=option.value,
        ))

    db.commit()
    db.refresh(question)
    return question_output(db, question)


def update_question(
    db: Session, question_id: UUID, data: QuestionUpdate
) -> dict:
    question = db.get(SurveyQuestion, question_id)

    if question is None:
        raise ValueError("Question not found.")

    require_draft_survey(db, question.survey_id)

    values = data.model_dump(exclude_unset=True)
    options = values.pop("options", None)
    new_type = values.get("question_type", question.question_type)

    if options is not None:
        if new_type in CHOICE_TYPES and len(options) < 2:
            raise ValueError("Choice questions require at least two answer options.")
        if new_type not in CHOICE_TYPES and options:
            raise ValueError("This question type does not accept answer options.")

    elif new_type in CHOICE_TYPES and question.question_type not in CHOICE_TYPES:
        raise ValueError("Provide at least two answer options for this question type.")

    for field, value in values.items():
        setattr(question, field, value)

    if options is not None:
        db.query(AnswerOption).filter(
            AnswerOption.question_id == question.id
        ).delete(synchronize_session=False)

        for index, option in enumerate(options):
            db.add(AnswerOption(
                question_id=question.id,
                order_index=index,
                label=option["label"],
                value=option["value"],
            ))

    db.commit()
    db.refresh(question)
    return question_output(db, question)


def delete_question(db: Session, question_id: UUID) -> None:
    question = db.get(SurveyQuestion, question_id)

    if question is None:
        raise ValueError("Question not found.")

    require_draft_survey(db, question.survey_id)
    db.delete(question)
    db.commit()


def list_public_questions(db: Session, survey_id: UUID) -> list[dict]:
    now = datetime.now(timezone.utc)

    survey = db.scalar(
        select(Survey).where(
            Survey.id == survey_id,
            Survey.status == "published",
            Survey.deleted_at.is_(None),
            (Survey.closes_at.is_(None) | (Survey.closes_at > now)),
            (
                Survey.participant_target.is_(None)
                | (Survey.participant_count < Survey.participant_target)
            ),
        )
    )

    if survey is None:
        raise ValueError("Survey not found.")

    # Only explicitly approved display settings are exposed to respondents.
    # Admin-only validation data remains private in the full question config.
    public_config_keys = {
        "placeholder", "min_length", "max_length",
        "min_value", "max_value", "min_date", "max_date",
        "step", "labels", "scale_labels", "allow_other",
        "other_label", "max_selections", "min_selections",
    }

    result = list_questions(db, survey_id)
    for item in result:
        config = item.get("config") or {}
        item["config"] = {
            key: value
            for key, value in config.items()
            if key in public_config_keys
        }

    return result
