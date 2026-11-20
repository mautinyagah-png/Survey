from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.database import engine, get_db
from app.models.identity import Role, User
from app.models.participations import Participation
from app.models.rewards import RewardRecord, Wallet, WalletTransaction
from app.models.surveys import Survey, SurveyQuestion
from app.security.dependencies import get_current_user


@contextmanager
def isolated_survey(validation_config):
    now = datetime.now(timezone.utc)
    connection = engine.connect()
    transaction = connection.begin()

    try:
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        role = db.scalar(select(Role).where(Role.name == "respondent"))
        assert role is not None, "Respondent role is missing."

        user = User(
            id=uuid4(),
            email=f"validation-{uuid4()}@test.invalid",
            full_name="Temporary Validation Respondent",
            password_hash="test-only",
            role_id=role.id,
            status="active",
            email_verified_at=now,
        )
        survey = Survey(
            id=uuid4(),
            slug=f"validation-test-{uuid4().hex[:10]}",
            title="Temporary Validation Test Survey",
            required_tier="basic",
            description="Temporary integration test",
            instructions="Answer the survey questions.",
            estimated_minutes=2,
            reward_amount=Decimal("30.00"),
            reward_currency="KES",
            status="published",
            published_at=now,
            participant_count=0,
            allow_repeat=False,
        )

        db.add_all([user, survey])
        db.flush()

        question = SurveyQuestion(
            survey_id=survey.id,
            order_index=0,
            question_type="short_text",
            prompt="Please answer the validation question.",
            is_required=True,
            config={"validation": validation_config},
        )
        db.add(question)
        db.commit()

        user_id = user.id
        survey_id = survey.id
        question_id = question.id
        db.close()

        def override_db():
            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                session.close()

        def override_user():
            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )
            try:
                return session.get(User, user_id)
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user

        yield TestClient(app), connection, user_id, survey_id, question_id

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()


def save_answer(client, participation_id, question_id, answer):
    return client.put(
        f"/api/participations/{participation_id}/responses",
        json={
            "answers": [
                {
                    "question_id": str(question_id),
                    "answer_text": answer,
                }
            ]
        },
    )


def verify_no_reward_or_wallet_credit(connection, participation_id, user_id):
    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )
    try:
        rewards = db.scalars(
            select(RewardRecord).where(
                RewardRecord.participation_id == participation_id
            )
        ).all()
        wallet_transactions = db.scalars(
            select(WalletTransaction).where(
                WalletTransaction.user_id == user_id
            )
        ).all()

        assert rewards == []
        assert wallet_transactions == []
    finally:
        db.close()


def test_screening_failure_disqualifies_immediately():
    rule = {
        "type": "screening",
        "eligible_values": ["employed", "self_employed"],
    }

    with isolated_survey(rule) as (
        client, connection, user_id, survey_id, question_id
    ):
        start = client.post(
            f"/api/surveys/{survey_id}/participations"
        )
        assert start.status_code == 201, start.text
        participation_id = start.json()["id"]

        save = save_answer(
            client, participation_id, question_id, "unemployed"
        )
        assert save.status_code == 200, save.text
        result = save.json()

        assert result["status"] == "disqualified"
        assert result["message"]
        assert "employed" not in result["message"].lower()
        assert "self_employed" not in result["message"].lower()

        # A disqualified attempt must not accept further answers or submission.
        another_save = save_answer(
            client, participation_id, question_id, "employed"
        )
        assert another_save.status_code == 409, another_save.text

        submit = client.post(
            f"/api/participations/{participation_id}/submit"
        )
        assert submit.status_code == 409, submit.text

        # A disqualified attempt counts as completed when repeat is disabled.
        another_start = client.post(
            f"/api/surveys/{survey_id}/participations"
        )
        assert another_start.status_code == 409, another_start.text

        db = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            participation = db.get(Participation, participation_id)
            survey = db.get(Survey, survey_id)

            assert participation.status == "disqualified"
            assert participation.submitted_at is not None
            assert survey.participant_count == 0
        finally:
            db.close()

        verify_no_reward_or_wallet_credit(
            connection, participation_id, user_id
        )


def test_attention_check_failure_disqualifies_on_submission():
    rule = {
        "type": "attention_check",
        "expected_values": ["blue"],
    }

    with isolated_survey(rule) as (
        client, connection, user_id, survey_id, question_id
    ):
        start = client.post(
            f"/api/surveys/{survey_id}/participations"
        )
        assert start.status_code == 201, start.text
        participation_id = start.json()["id"]

        save = save_answer(
            client, participation_id, question_id, "green"
        )
        assert save.status_code == 200, save.text
        assert save.json()["status"] == "in_progress"

        submit = client.post(
            f"/api/participations/{participation_id}/submit"
        )
        assert submit.status_code == 200, submit.text
        assert submit.json()["status"] == "disqualified"

        db = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            participation = db.get(Participation, participation_id)
            survey = db.get(Survey, survey_id)

            assert participation.status == "disqualified"
            assert participation.submitted_at is not None
            assert survey.participant_count == 0
        finally:
            db.close()

        verify_no_reward_or_wallet_credit(
            connection, participation_id, user_id
        )


def test_correct_attention_check_allows_submission_and_pending_reward():
    rule = {
        "type": "attention_check",
        "expected_values": ["blue"],
    }

    with isolated_survey(rule) as (
        client, connection, user_id, survey_id, question_id
    ):
        start = client.post(
            f"/api/surveys/{survey_id}/participations"
        )
        assert start.status_code == 201, start.text
        participation_id = start.json()["id"]

        save = save_answer(
            client, participation_id, question_id, "Blue"
        )
        assert save.status_code == 200, save.text
        assert save.json()["status"] == "in_progress"

        submit = client.post(
            f"/api/participations/{participation_id}/submit"
        )
        assert submit.status_code == 200, submit.text
        assert submit.json()["status"] == "submitted"

        db = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            participation = db.get(Participation, participation_id)
            survey = db.get(Survey, survey_id)

            rewards = db.scalars(
                select(RewardRecord).where(
                    RewardRecord.participation_id == participation_id
                )
            ).all()
            wallet_transactions = db.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.user_id == user_id
                )
            ).all()

            assert participation.status == "submitted"
            assert survey.participant_count == 1
            assert len(rewards) == 1
            assert rewards[0].status == "pending"
            assert rewards[0].amount == Decimal("30.00")
            assert rewards[0].currency.strip() == "KES"
            assert len(wallet_transactions) == 1

            wallet_transaction = wallet_transactions[0]
            assert wallet_transaction.type == "pending_credit"
            assert wallet_transaction.amount == Decimal("30.00")
            assert wallet_transaction.currency.strip() == "KES"
            assert wallet_transaction.reference_type == "reward"
            assert wallet_transaction.reference_id == rewards[0].id

            wallet = db.scalar(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == "KES",
                )
            )

            assert wallet is not None
            assert wallet.pending_balance == Decimal("30.00")
            assert wallet.available_balance == Decimal("0.00")
            assert wallet.total_earned == Decimal("0.00")
        finally:
            db.close()


def test_public_question_api_does_not_expose_private_validation_config():
    rule = {
        "type": "screening",
        "eligible_values": ["employed", "self_employed"],
        "expected_values": ["blue"],
    }

    with isolated_survey(rule) as (
        client, connection, user_id, survey_id, question_id
    ):
        response = client.get(
            f"/api/surveys/{survey_id}/questions"
        )

        assert response.status_code == 200, response.text
        questions = response.json()

        assert len(questions) == 1
        assert questions[0]["id"] == str(question_id)

        public_config = questions[0]["config"]
        assert "validation" not in public_config
        assert "eligible_values" not in response.text
        assert "expected_values" not in response.text
        assert "employed" not in response.text
        assert "self_employed" not in response.text
        assert "blue" not in response.text
