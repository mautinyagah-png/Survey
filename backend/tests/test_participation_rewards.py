from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.database import engine, get_db
from app.models.identity import EmailVerification, Role, User, UserPreference
from app.models.surveys import Survey, SurveyQuestion
from app.models.participations import Participation
from app.models.rewards import RewardRecord, Wallet, WalletTransaction
from app.schemas.auth import RegisterRequest
from app.services.auth import register_user
from app.security.dependencies import get_current_user


def test_submission_creates_pending_reward_and_pending_wallet_credit():
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
            email=f"participation-{uuid4()}@example.com",
            full_name="Temporary Participation Respondent",
            password_hash="test-only",
            role_id=role.id,
            status="active",
            email_verified_at=now,
        )
        db.add(user)

        survey = Survey(
            id=uuid4(),
            slug=f"participation-test-{uuid4().hex[:10]}",
            title="Temporary Reward Test Survey",
            required_tier="basic",
            description="Temporary integration test",
            instructions="Answer the required question.",
            estimated_minutes=2,
            reward_amount=Decimal("25.00"),
            reward_currency="KES",
            status="published",
            published_at=now,
            participant_count=0,
            allow_repeat=False,
        )
        db.add(survey)
        db.flush()

        question = SurveyQuestion(
            survey_id=survey.id,
            order_index=0,
            question_type="short_text",
            prompt="What is your favourite colour?",
            is_required=True,
            config={},
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
            check_session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )
            try:
                return check_session.get(User, user_id)
            finally:
                check_session.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user

        client = TestClient(app)

        # Start participation.
        start = client.post(
            f"/api/surveys/{survey_id}/participations"
        )
        assert start.status_code == 201, start.text
        participation_id = start.json()["id"]

        # Save the required answer.
        save = client.put(
            f"/api/participations/{participation_id}/responses",
            json={
                "answers": [
                    {
                        "question_id": str(question_id),
                        "answer_text": "Blue",
                    }
                ]
            },
        )
        assert save.status_code == 200, save.text
        assert save.json()["saved"] == 1

        # Submit the survey.
        submit = client.post(
            f"/api/participations/{participation_id}/submit"
        )
        assert submit.status_code == 200, submit.text
        assert submit.json()["status"] == "submitted"

        # Verify the reward and wallet accounting.
        verify_db = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            rewards = verify_db.scalars(
                select(RewardRecord).where(
                    RewardRecord.participation_id == participation_id
                )
            ).all()

            assert len(rewards) == 1
            assert rewards[0].user_id == user_id
            assert rewards[0].survey_id == survey_id
            assert rewards[0].amount == Decimal("25.00")
            assert rewards[0].currency.strip() == "KES"
            assert rewards[0].status == "pending"

            wallet_transactions = verify_db.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.user_id == user_id
                )
            ).all()

            assert len(wallet_transactions) == 1
            assert wallet_transactions[0].type == "pending_credit"
            assert wallet_transactions[0].amount == Decimal("25.00")
            assert wallet_transactions[0].currency.strip() == "KES"
            assert wallet_transactions[0].reference_type == "reward"
            assert wallet_transactions[0].reference_id == rewards[0].id

            wallet = verify_db.scalar(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == "KES",
                )
            )
            assert wallet is not None
            assert wallet.pending_balance == Decimal("25.00")
            assert wallet.available_balance == Decimal("0.00")
            assert wallet.total_earned == Decimal("0.00")

            participation = verify_db.get(
                Participation, participation_id
            )
            assert participation.status == "submitted"

            print("PASS: Participation submitted successfully.")
            print("PASS: Exactly one pending reward was created.")
            print("PASS: Reward amount is KES 25.00.")
            print("PASS: Pending wallet balance is KES 25.00.")
            print("PASS: Available balance remains KES 0.00.")
        finally:
            verify_db.close()

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()
        print("Temporary integration-test data rolled back.")



def test_registration_creates_zero_balance_wallet():
    connection = engine.connect()
    transaction = connection.begin()

    try:
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        data = RegisterRequest(
            full_name="Temporary Wallet Respondent",
            email=f"wallet-{uuid4()}@example.com",
            password="SecureTestPassword123!",
            country_code="KE",
        )

        user, verification_token = register_user(db, data)

        assert user.id is not None
        assert verification_token

        wallet = db.scalar(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        assert wallet is not None
        assert wallet.currency.strip() == "KES"
        assert wallet.pending_balance == Decimal("0.00")
        assert wallet.available_balance == Decimal("0.00")
        assert wallet.total_earned == Decimal("0.00")

        preference = db.get(UserPreference, user.id)
        assert preference is not None

        verification = db.scalar(
            select(EmailVerification).where(
                EmailVerification.user_id == user.id
            )
        )
        assert verification is not None

        transactions = db.scalars(
            select(WalletTransaction).where(
                WalletTransaction.user_id == user.id
            )
        ).all()
        assert transactions == []

        print("PASS: Registration created the respondent account.")
        print("PASS: Registration created its KES wallet immediately.")
        print("PASS: All three wallet balances start at zero.")
        print("PASS: Preferences and email verification were created.")
        print("PASS: No unnecessary wallet transactions were recorded.")

        db.close()

    finally:
        transaction.rollback()
        connection.close()
        print("Temporary registration-test data rolled back.")
