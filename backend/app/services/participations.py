"""Business logic for starting, answering and submitting surveys."""

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.participations import Participation, Response
from app.models.surveys import AnswerOption, Survey, SurveyQuestion
from app.models.identity import User
from app.models.rewards import RewardRecord, Wallet, WalletTransaction
from app.services.subscriptions import (
    can_access_tier,
    get_effective_subscription,
)


class ParticipationError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_open_survey(db: Session, survey_id: UUID) -> Survey:
    now = datetime.now(timezone.utc)
    survey = db.scalar(
        select(Survey)
        .where(
            Survey.id == survey_id,
            Survey.deleted_at.is_(None),
        )
        .with_for_update()
    )

    if survey is None:
        raise ParticipationError("Survey not found.", 404)

    if survey.status != "published":
        raise ParticipationError("This survey is not available.", 404)

    if survey.closes_at is not None and survey.closes_at <= now:
        raise ParticipationError("This survey has closed.", 409)

    if (
        survey.participant_target is not None
        and survey.participant_count >= survey.participant_target
    ):
        raise ParticipationError("This survey has reached its participant limit.", 409)

    return survey


def _check_tier(db: Session, user: User, survey: Survey) -> None:
    tier_rank = get_effective_subscription(db, user.id)["tier_rank"]

    if not can_access_tier(tier_rank, survey.required_tier):
        raise ParticipationError(
            f"Upgrade to {survey.required_tier.title()} to participate in this survey.",
            403,
        )


def start_participation(
    db: Session,
    user: User,
    survey_id: UUID,
) -> Participation:
    survey = _get_open_survey(db, survey_id)
    _check_tier(db, user, survey)

    existing = db.scalars(
        select(Participation)
        .where(
            Participation.user_id == user.id,
            Participation.survey_id == survey.id,
        )
        .order_by(Participation.created_at.desc())
        .with_for_update()
    ).all()

    active = next(
        (item for item in existing if item.status == "in_progress"),
        None,
    )

    if active is not None:
        db.commit()
        return active

    completed_statuses = {
        "submitted", "under_review", "approved", "rejected",
        "disqualified",
    }

    if not survey.allow_repeat and any(
        item.status in completed_statuses for item in existing
    ):
        raise ParticipationError(
            "You have already participated in this survey."
        )

    participation = Participation(
        user_id=user.id,
        survey_id=survey.id,
        status="in_progress",
    )
    db.add(participation)
    db.commit()
    db.refresh(participation)
    return participation


def _get_owned_participation(
    db: Session,
    user: User,
    participation_id: UUID,
    lock: bool = False,
) -> Participation:
    query = select(Participation).where(
        Participation.id == participation_id,
        Participation.user_id == user.id,
    )

    if lock:
        query = query.with_for_update()

    participation = db.scalar(query)

    if participation is None:
        raise ParticipationError("Participation not found.", 404)

    if participation.status != "in_progress":
        raise ParticipationError(
            "This participation is no longer accepting changes."
        )

    return participation


def _is_empty_answer(answer) -> bool:
    return (
        answer.answer_text is None or not answer.answer_text.strip()
    ) and answer.rating_value is None and not answer.selected_option_ids


def _validate_answer(
    db: Session,
    question: SurveyQuestion,
    answer,
) -> bool:
    """Validate an answer. Return False when the answer should be cleared."""

    if _is_empty_answer(answer):
        return False

    kind = question.question_type
    config = question.config or {}

    if kind in {"single_choice", "dropdown", "multi_select"}:
        selected = answer.selected_option_ids or []

        if answer.answer_text is not None or answer.rating_value is not None:
            raise ParticipationError("Invalid answer format for a choice question.", 422)

        if kind in {"single_choice", "dropdown"} and len(selected) != 1:
            raise ParticipationError("Select exactly one answer option.", 422)

        if kind == "multi_select" and not selected:
            raise ParticipationError("Select at least one answer option.", 422)

        if len(selected) != len(set(selected)):
            raise ParticipationError("Duplicate answer options are not allowed.", 422)

        valid_ids = set(db.scalars(
            select(AnswerOption.id).where(
                AnswerOption.question_id == question.id,
                AnswerOption.id.in_(selected),
            )
        ).all())

        if valid_ids != set(selected):
            raise ParticipationError(
                "One or more selected options do not belong to this question.",
                422,
            )

    elif kind == "yes_no":
        if answer.rating_value is not None or answer.selected_option_ids:
            raise ParticipationError("Invalid answer format for yes/no question.", 422)

        if answer.answer_text.strip().lower() not in {"yes", "no"}:
            raise ParticipationError("Answer must be yes or no.", 422)

    elif kind == "rating":
        if answer.answer_text is not None or answer.selected_option_ids:
            raise ParticipationError("Invalid answer format for rating question.", 422)

        if answer.rating_value is None:
            raise ParticipationError("A rating is required.", 422)

        minimum = int(config.get("min_value", 1))
        maximum = int(config.get("max_value", 10))

        if not 1 <= minimum <= maximum <= 10:
            raise ParticipationError("The survey contains an invalid rating configuration.")

        if not minimum <= answer.rating_value <= maximum:
            raise ParticipationError(
                f"Rating must be between {minimum} and {maximum}.",
                422,
            )

    elif kind in {"short_text", "long_text"}:
        if answer.rating_value is not None or answer.selected_option_ids:
            raise ParticipationError("Invalid answer format for text question.", 422)

        value = answer.answer_text.strip()
        maximum = int(config.get(
            "max_length", 500 if kind == "short_text" else 10000
        ))
        minimum = int(config.get("min_length", 0))

        if maximum < 1 or maximum > 10000 or minimum < 0 or minimum > maximum:
            raise ParticipationError("The survey contains an invalid text configuration.")

        if len(value) > maximum or len(value) < minimum:
            raise ParticipationError(
                f"Answer must contain between {minimum} and {maximum} characters.",
                422,
            )

    elif kind == "date":
        if answer.rating_value is not None or answer.selected_option_ids:
            raise ParticipationError("Invalid answer format for date question.", 422)

        try:
            date.fromisoformat(answer.answer_text.strip())
        except (ValueError, AttributeError):
            raise ParticipationError(
                "Enter a valid date in YYYY-MM-DD format.",
                422,
            )

    else:
        raise ParticipationError("Unsupported question type.")

    return True


def _get_validation_rule(question: SurveyQuestion):
    config = question.config or {}
    validation = config.get("validation")

    if validation is None:
        return None

    if not isinstance(validation, dict):
        raise ParticipationError(
            "The survey contains an invalid validation configuration."
        )

    rule_type = validation.get("type")

    if rule_type == "screening":
        expected = validation.get("eligible_values")
    elif rule_type == "attention_check":
        expected = validation.get("expected_values")
    else:
        raise ParticipationError(
            "The survey contains an invalid validation configuration."
        )

    if (
        not isinstance(expected, list)
        or not expected
        or any(not isinstance(value, str) or not value.strip()
               for value in expected)
    ):
        raise ParticipationError(
            "The survey contains an invalid validation configuration."
        )

    return {
        "type": rule_type,
        "expected": {value.strip().casefold() for value in expected},
    }


def _response_values(
    db: Session,
    question: SurveyQuestion,
    response: Response,
) -> set[str]:
    if question.question_type in {
        "single_choice", "dropdown", "multi_select"
    }:
        option_ids = response.selected_option_ids or []

        if not option_ids:
            return set()

        values = db.scalars(
            select(AnswerOption.value).where(
                AnswerOption.question_id == question.id,
                AnswerOption.id.in_(option_ids),
            )
        ).all()

        return {value.strip().casefold() for value in values}

    if question.question_type == "rating":
        if response.rating_value is None:
            return set()
        return {str(response.rating_value)}

    if response.answer_text is None:
        return set()

    return {response.answer_text.strip().casefold()}


def _validation_passes(
    db: Session,
    question: SurveyQuestion,
    response: Response | None,
    rule: dict,
) -> bool:
    # An unanswered screening question is evaluated when an answer exists.
    # An unanswered attention check fails at submission.
    if response is None:
        return rule["type"] == "screening"

    actual = _response_values(db, question, response)
    expected = rule["expected"]

    if question.question_type == "multi_select":
        if rule["type"] == "screening":
            # At least one selected option must meet the eligibility criteria.
            return bool(actual.intersection(expected))

        # Attention-check multi-select answers must match the expected set.
        return actual == expected

    return len(actual) == 1 and actual.issubset(expected)


def _has_failed_validation(
    db: Session,
    questions: list[SurveyQuestion],
    response_map: dict,
    rule_type: str,
) -> bool:
    for question in questions:
        rule = _get_validation_rule(question)

        if rule is None or rule["type"] != rule_type:
            continue

        response = response_map.get(question.id)

        if not _validation_passes(db, question, response, rule):
            return True

    return False


def _mark_disqualified(
    participation: Participation,
    db: Session,
) -> None:
    now = datetime.now(timezone.utc)
    participation.status = "disqualified"
    participation.submitted_at = now
    participation.updated_at = now
    db.commit()
    db.refresh(participation)


def save_responses(
    db: Session,
    user: User,
    participation_id: UUID,
    answers: list,
) -> dict:
    participation = _get_owned_participation(
        db, user, participation_id, lock=True
    )

    question_ids = [item.question_id for item in answers]

    if len(question_ids) != len(set(question_ids)):
        raise ParticipationError(
            "A question can only appear once in each save request.",
            422,
        )

    questions = db.scalars(
        select(SurveyQuestion).where(
            SurveyQuestion.survey_id == participation.survey_id,
            SurveyQuestion.id.in_(question_ids),
        )
    ).all()
    question_map = {item.id: item for item in questions}

    if len(question_map) != len(question_ids):
        raise ParticipationError(
            "One or more questions do not belong to this survey.",
            422,
        )

    saved = 0
    cleared = 0

    try:
        for answer in answers:
            question = question_map[answer.question_id]
            existing = db.scalar(
                select(Response).where(
                    Response.participation_id == participation.id,
                    Response.question_id == question.id,
                ).with_for_update()
            )

            if not _validate_answer(db, question, answer):
                if existing is not None:
                    db.delete(existing)
                    cleared += 1
                continue

            if existing is None:
                existing = Response(
                    participation_id=participation.id,
                    question_id=question.id,
                )
                db.add(existing)

            existing.answer_text = (
                answer.answer_text.strip()
                if answer.answer_text is not None else None
            )
            existing.rating_value = answer.rating_value
            existing.selected_option_ids = (
                answer.selected_option_ids
                if answer.selected_option_ids else None
            )
            existing.updated_at = datetime.now(timezone.utc)
            saved += 1

        # Evaluate screening questions on the server after saving answers.
        questions_for_screening = db.scalars(
            select(SurveyQuestion).where(
                SurveyQuestion.survey_id == participation.survey_id
            )
        ).all()

        responses_for_screening = db.scalars(
            select(Response).where(
                Response.participation_id == participation.id
            )
        ).all()

        response_map = {
            item.question_id: item for item in responses_for_screening
        }

        screening_failed = _has_failed_validation(
            db,
            questions_for_screening,
            response_map,
            "screening",
        )

        if screening_failed:
            now = datetime.now(timezone.utc)
            participation.status = "disqualified"
            participation.submitted_at = now
            participation.updated_at = now
            db.commit()

            return {
                "saved": saved,
                "cleared": cleared,
                "status": "disqualified",
                "message": (
                    "You do not meet the eligibility requirements "
                    "for this survey."
                ),
            }

        db.commit()
        return {
            "saved": saved,
            "cleared": cleared,
            "status": participation.status,
            "message": None,
        }

    except Exception:
        db.rollback()
        raise


def submit_participation(
    db: Session,
    user: User,
    participation_id: UUID,
) -> Participation:
    participation = _get_owned_participation(
        db, user, participation_id, lock=True
    )

    survey = db.scalar(
        select(Survey)
        .where(Survey.id == participation.survey_id)
        .with_for_update()
    )

    if survey is None or survey.deleted_at is not None:
        raise ParticipationError("Survey not found.", 404)

    _check_tier(db, user, survey)

    questions = db.scalars(
        select(SurveyQuestion).where(
            SurveyQuestion.survey_id == survey.id
        )
    ).all()

    responses = db.scalars(
        select(Response).where(
            Response.participation_id == participation.id
        )
    ).all()
    response_map = {item.question_id: item for item in responses}

    screening_failed = _has_failed_validation(
        db, questions, response_map, "screening"
    )
    attention_failed = _has_failed_validation(
        db, questions, response_map, "attention_check"
    )

    if screening_failed or attention_failed:
        _mark_disqualified(participation, db)
        return participation

    for question in questions:
        if not question.is_required:
            continue

        response = response_map.get(question.id)

        if response is None:
            raise ParticipationError(
                f"Please answer the required question: {question.prompt}",
                422,
            )

        if (
            response.answer_text is None
            and response.rating_value is None
            and not response.selected_option_ids
        ):
            raise ParticipationError(
                f"Please answer the required question: {question.prompt}",
                422,
            )

    if (
        survey.participant_target is not None
        and survey.participant_count >= survey.participant_target
    ):
        raise ParticipationError(
            "This survey has reached its participant limit."
        )

    now = datetime.now(timezone.utc)
    # Create the pending reward in the same transaction as submission.
    # Never credit withdrawable wallet funds at this stage.
    existing_reward = db.scalar(
        select(RewardRecord).where(
            RewardRecord.participation_id == participation.id
        )
    )

    if existing_reward is None:
        reward = RewardRecord(
            participation_id=participation.id,
            user_id=user.id,
            survey_id=survey.id,
            amount=survey.reward_amount,
            currency=survey.reward_currency,
            status="pending",
        )
        db.add(reward)
        db.flush()

        # Create this user's wallet for the reward currency if necessary.
        db.execute(
            pg_insert(Wallet)
            .values(
                user_id=user.id,
                currency=survey.reward_currency,
            )
            .on_conflict_do_nothing(
                index_elements=[Wallet.user_id, Wallet.currency]
            )
        )

        # Lock the wallet row before changing its balance.
        wallet = db.scalar(
            select(Wallet)
            .where(
                Wallet.user_id == user.id,
                Wallet.currency == survey.reward_currency,
            )
            .with_for_update()
        )
        if wallet is None:
            raise RuntimeError("Could not create or retrieve the reward wallet.")

        wallet.pending_balance += reward.amount
        wallet.updated_at = now

        db.add(
            WalletTransaction(
                user_id=user.id,
                type="pending_credit",
                amount=reward.amount,
                currency=reward.currency,
                reference_type="reward",
                reference_id=reward.id,
                description="Survey reward submitted; awaiting approval.",
            )
        )

    participation.status = "submitted"
    participation.submitted_at = now
    participation.updated_at = now
    survey.participant_count += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(participation)
    return participation
