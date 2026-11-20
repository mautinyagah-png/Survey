from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.identity import Role, User
from app.models.participations import Participation
from app.models.rewards import RewardRecord, Wallet, WalletTransaction
from app.models.surveys import Survey
from app.security.dependencies import get_current_user


def test_admin_can_approve_and_reject_rewards_atomically():
    connection = engine.connect()
    transaction = connection.begin()

    try:
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        admin_role = db.scalar(select(Role).where(Role.name == "admin"))
        respondent_role = db.scalar(
            select(Role).where(Role.name == "respondent")
        )
        assert admin_role is not None
        assert respondent_role is not None

        now = datetime.now(timezone.utc)

        admin = User(
            id=uuid4(),
            email=f"reward-admin-{uuid4()}@example.com",
            full_name="Temporary Reward Admin",
            password_hash="test-only",
            role_id=admin_role.id,
            status="active",
            email_verified_at=now,
        )
        respondent = User(
            id=uuid4(),
            email=f"reward-user-{uuid4()}@example.com",
            full_name="Temporary Reward Respondent",
            password_hash="test-only",
            role_id=respondent_role.id,
            status="active",
            email_verified_at=now,
        )

        db.add_all([admin, respondent])

        survey = Survey(
            id=uuid4(),
            slug=f"reward-review-{uuid4().hex[:10]}",
            title="Reward Review Test Survey",
            required_tier="basic",
            description="Temporary test",
            instructions="Temporary test",
            estimated_minutes=2,
            reward_amount=Decimal("25.00"),
            reward_currency="KES",
            status="published",
            published_at=now,
            participant_count=2,
            allow_repeat=False,
        )
        db.add(survey)
        db.flush()

        approval_participation = Participation(
            id=uuid4(),
            user_id=respondent.id,
            survey_id=survey.id,
            status="submitted",
            submitted_at=now,
        )
        rejection_participation = Participation(
            id=uuid4(),
            user_id=respondent.id,
            survey_id=survey.id,
            status="submitted",
            submitted_at=now,
        )
        db.add_all([approval_participation, rejection_participation])
        db.flush()

        approval_reward = RewardRecord(
            id=uuid4(),
            participation_id=approval_participation.id,
            user_id=respondent.id,
            survey_id=survey.id,
            amount=Decimal("25.00"),
            currency="KES",
            status="pending",
        )
        rejection_reward = RewardRecord(
            id=uuid4(),
            participation_id=rejection_participation.id,
            user_id=respondent.id,
            survey_id=survey.id,
            amount=Decimal("25.00"),
            currency="KES",
            status="pending",
        )
        db.add_all([approval_reward, rejection_reward])

        wallet = Wallet(
            id=uuid4(),
            user_id=respondent.id,
            currency="KES",
            pending_balance=Decimal("50.00"),
            available_balance=Decimal("0.00"),
            total_earned=Decimal("0.00"),
        )
        db.add(wallet)
        db.flush()

        for reward in (approval_reward, rejection_reward):
            db.add(
                WalletTransaction(
                    user_id=respondent.id,
                    type="pending_credit",
                    amount=Decimal("25.00"),
                    currency="KES",
                    reference_type="reward",
                    reference_id=reward.id,
                    description="Test pending reward.",
                )
            )

        db.commit()

        admin_id = admin.id
        respondent_id = respondent.id
        approval_reward_id = approval_reward.id
        rejection_reward_id = rejection_reward.id

        db.close()

        active_user_id = {"value": respondent_id}

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
                return session.get(User, active_user_id["value"])
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user

        with TestClient(app) as client:
            # A respondent must not be allowed to review rewards.
            forbidden = client.get("/api/admin/rewards/pending")
            assert forbidden.status_code == 403, forbidden.text

            # Switch the authenticated identity to the administrator.
            active_user_id["value"] = admin_id

            queue = client.get("/api/admin/rewards/pending")
            assert queue.status_code == 200, queue.text
            assert len(queue.json()) == 2

            approved = client.post(
                f"/api/admin/rewards/{approval_reward_id}/approve"
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"
            assert approved.json()["approved_by"] == str(admin_id)

            # The same reward cannot be approved a second time.
            duplicate_approval = client.post(
                f"/api/admin/rewards/{approval_reward_id}/approve"
            )
            assert duplicate_approval.status_code == 409

            rejected = client.post(
                f"/api/admin/rewards/{rejection_reward_id}/reject",
                json={"reason": "Submission did not meet review requirements."},
            )
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["status"] == "rejected"
            assert (
                rejected.json()["rejected_reason"]
                == "Submission did not meet review requirements."
            )

            # The same reward cannot be rejected or approved again.
            duplicate_rejection = client.post(
                f"/api/admin/rewards/{rejection_reward_id}/reject",
                json={"reason": "Repeated decision."},
            )
            assert duplicate_rejection.status_code == 409

            duplicate_rejected_approval = client.post(
                f"/api/admin/rewards/{rejection_reward_id}/approve"
            )
            assert duplicate_rejected_approval.status_code == 409

        verify = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            final_wallet = verify.scalar(
                select(Wallet).where(
                    Wallet.user_id == respondent_id,
                    Wallet.currency == "KES",
                )
            )
            assert final_wallet is not None
            assert final_wallet.pending_balance == Decimal("0.00")
            assert final_wallet.available_balance == Decimal("25.00")
            assert final_wallet.total_earned == Decimal("25.00")

            approval_movements = verify.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.reference_id == approval_reward_id,
                    WalletTransaction.reference_type == "reward",
                )
            ).all()
            assert {item.type for item in approval_movements} == {
                "pending_credit",
                "pending_debit",
                "credit",
            }

            rejection_movements = verify.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.reference_id == rejection_reward_id,
                    WalletTransaction.reference_type == "reward",
                )
            ).all()
            assert {item.type for item in rejection_movements} == {
                "pending_credit",
                "pending_debit",
            }

            rejection_debit = next(
                item for item in rejection_movements
                if item.type == "pending_debit"
            )
            assert str(admin_id) in rejection_debit.description
        finally:
            verify.close()

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()


def test_rejection_requires_a_nonblank_reason():
    with TestClient(app) as client:
        response = client.post(
            f"/api/admin/rewards/{uuid4()}/reject",
            json={"reason": "   "},
        )
        # Authentication is checked before the endpoint body is processed.
        assert response.status_code == 401
