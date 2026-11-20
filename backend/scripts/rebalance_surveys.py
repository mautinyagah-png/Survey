"""Rebalance surveys per user spec. Updates by slug, creates missing, never deletes."""

from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select

from app.database import SessionLocal
from app.models.question_bank import (
    QuestionBankOption, QuestionBankQuestion, QuestionBankTitle,
)
from app.models.surveys import AnswerOption, Survey, SurveyQuestion
from app.services.surveys import make_unique_slug

REWARDS = {
    "basic":    [Decimal("40.00"), Decimal("50.00"), Decimal("55.00"), Decimal("60.00")],
    "bronze":   [Decimal("50.00"), Decimal("60.00"), Decimal("70.00"), Decimal("80.00")],
    "silver":   [Decimal("50.00"), Decimal("60.00"), Decimal("70.00"), Decimal("80.00")],
    "gold":     [Decimal("60.00"), Decimal("70.00"), Decimal("80.00"), Decimal("90.00")],
    "platinum": [Decimal("60.00"), Decimal("70.00"), Decimal("80.00"), Decimal("90.00"), Decimal("100.00")],
}
MINUTES = {"basic": 4, "bronze": 5, "silver": 6, "gold": 7, "platinum": 8}


def main():
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    titles = db.scalars(
        select(QuestionBankTitle).order_by(QuestionBankTitle.sort_order, QuestionBankTitle.title)
    ).all()
    total = len(titles)
    basic_count = 10
    remaining = total - basic_count
    per_rest = remaining // 4
    extra = remaining % 4

    counts = {
        "basic": basic_count,
        "bronze": per_rest + (1 if extra >= 1 else 0),
        "silver": per_rest + (1 if extra >= 2 else 0),
        "gold":   per_rest + (1 if extra >= 3 else 0),
        "platinum": per_rest,
    }

    tiers = (["basic"] * counts["basic"]
             + ["bronze"] * counts["bronze"]
             + ["silver"] * counts["silver"]
             + ["gold"] * counts["gold"]
             + ["platinum"] * counts["platinum"])

    created = updated = 0
    reward_idx = {k: 0 for k in REWARDS}

    for i, title in enumerate(titles):
        tier = tiers[i]
        rl = REWARDS[tier]
        reward = rl[reward_idx[tier] % len(rl)]
        reward_idx[tier] += 1

        existing = db.scalar(select(Survey).where(Survey.slug == title.slug))
        if existing:
            existing.required_tier = tier
            existing.reward_amount = reward
            existing.reward_currency = "KES"
            existing.estimated_minutes = MINUTES[tier]
            existing.country_code = "KE"
            existing.target_audience = existing.target_audience or "Adults in Kenya"
            if existing.status == "draft":
                existing.status = "published"
                existing.published_at = now
            updated += 1
            continue

        survey = Survey(
            slug=make_unique_slug(db, title.slug, title.slug),
            title=title.title,
            required_tier=tier,
            description=title.description or f"Tell us about {title.title.lower()}.",
            instructions="Answer all questions honestly. Your responses are anonymous.",
            country_code="KE",
            target_audience="Adults in Kenya",
            estimated_minutes=MINUTES[tier],
            reward_amount=reward,
            reward_currency="KES",
            status="published",
            published_at=now,
            participant_count=0,
            allow_repeat=False,
        )
        db.add(survey); db.flush()

        for bq in db.scalars(
            select(QuestionBankQuestion)
            .where(QuestionBankQuestion.title_id == title.id)
            .order_by(QuestionBankQuestion.order_index)
        ).all():
            sq = SurveyQuestion(
                survey_id=survey.id,
                order_index=bq.order_index,
                question_type=bq.question_type,
                prompt=bq.prompt,
                help_text=bq.help_text,
                is_required=bq.is_required,
                config=bq.config or {},
            )
            db.add(sq); db.flush()
            for opt in db.scalars(
                select(QuestionBankOption)
                .where(QuestionBankOption.question_id == bq.id)
                .order_by(QuestionBankOption.order_index)
            ).all():
                db.add(AnswerOption(
                    question_id=sq.id,
                    order_index=opt.order_index,
                    label=opt.label,
                    value=opt.value,
                ))
        created += 1

    db.commit()
    print(f"Surveys created: {created}")
    print(f"Surveys updated: {updated}")
    print(f"Distribution: {counts}")
    db.close()


if __name__ == "__main__":
    main()
