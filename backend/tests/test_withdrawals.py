from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.administration import AuditLog, WithdrawalRequest
from app.models.identity import Role, User
from app.models.rewards import Wallet, WalletTransaction
from app.security.dependencies import get_current_user


def test_withdrawal_reservation_rejection_and_payout_workflow():
    connection = engine.connect()
    transaction = connection.begin()

    try:
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        now = datetime.now(timezone.utc)

        respondent_role = db.scalar(
            select(Role).where(Role.name == "respondent")
        )
        admin_role = db.scalar(select(Role).where(Role.name == "admin"))
        assert respondent_role is not None
        assert admin_role is not None

        respondent = User(
            id=uuid4(),
            email=f"withdraw-user-{uuid4()}@example.com",
            full_name="Temporary Withdrawal User",
            password_hash="test-only",
            role_id=respondent_role.id,
            status="active",
            email_verified_at=now,
        )
        admin = User(
            id=uuid4(),
            email=f"withdraw-admin-{uuid4()}@example.com",
            full_name="Temporary Withdrawal Admin",
            password_hash="test-only",
            role_id=admin_role.id,
            status="active",
            email_verified_at=now,
        )
        db.add_all([respondent, admin])
        db.flush()

        wallet = Wallet(
            id=uuid4(),
            user_id=respondent.id,
            currency="KES",
            pending_balance=Decimal("0.00"),
            available_balance=Decimal("100.00"),
            total_earned=Decimal("100.00"),
        )
        db.add(wallet)
        db.commit()

        respondent_id = respondent.id
        admin_id = admin.id
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
            # A withdrawal reserves money immediately.
            requested = client.post(
                "/api/wallet/me/withdrawals",
                json={
                    "amount": "40.00",
                    "currency": "KES",
                    "method": "mpesa",
                    "destination_masked": "+2547****123",
                },
            )
            assert requested.status_code == 201, requested.text
            first_id = requested.json()["id"]
            assert requested.json()["status"] == "requested"

            own_list = client.get("/api/wallet/me/withdrawals")
            assert own_list.status_code == 200
            assert own_list.json()["total"] == 1

            balances = client.get("/api/wallet/me")
            assert balances.status_code == 200
            assert balances.json()[0]["available_balance"] == "60.00"

            # Cannot reserve more than the remaining available balance.
            insufficient = client.post(
                "/api/wallet/me/withdrawals",
                json={
                    "amount": "61.00",
                    "currency": "KES",
                    "method": "mpesa",
                    "destination_masked": "+2547****123",
                },
            )
            assert insufficient.status_code == 409

            # Switch to administrator for review.
            active_user_id["value"] = admin_id

            queue = client.get("/api/admin/withdrawals")
            assert queue.status_code == 200
            assert queue.json()["total"] == 1

            approved = client.post(
                f"/api/admin/withdrawals/{first_id}/approve",
                json={"notes": "Verified for payout."},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"

            processing = client.post(
                f"/api/admin/withdrawals/{first_id}/processing",
                json={"notes": "Payout initiated."},
            )
            assert processing.status_code == 200, processing.text
            assert processing.json()["status"] == "processing"

            paid = client.post(
                f"/api/admin/withdrawals/{first_id}/paid",
                params={"payment_reference": "MPESA-TEST-001"},
            )
            assert paid.status_code == 200, paid.text
            assert paid.json()["status"] == "paid"

            duplicate_paid = client.post(
                f"/api/admin/withdrawals/{first_id}/paid",
                params={"payment_reference": "MPESA-TEST-002"},
            )
            assert duplicate_paid.status_code == 409

            # A second withdrawal is rejected and its hold is released.
            active_user_id["value"] = respondent_id
            second = client.post(
                "/api/wallet/me/withdrawals",
                json={
                    "amount": "20.00",
                    "currency": "KES",
                    "method": "bank_transfer",
                    "destination_masked": "****5678",
                },
            )
            assert second.status_code == 201, second.text
            second_id = second.json()["id"]

            active_user_id["value"] = admin_id
            rejected = client.post(
                f"/api/admin/withdrawals/{second_id}/reject",
                json={"notes": "Recipient details require verification."},
            )
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["status"] == "rejected"

            duplicate_rejection = client.post(
                f"/api/admin/withdrawals/{second_id}/reject",
                json={"notes": "Repeated rejection."},
            )
            assert duplicate_rejection.status_code == 409

        verify = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            final_wallet = verify.scalar(
                select(Wallet).where(Wallet.user_id == respondent_id)
            )
            assert final_wallet is not None
            # 100 - 40 paid = 60 available; rejected 20 was released.
            assert final_wallet.available_balance == Decimal("60.00")
            assert final_wallet.pending_balance == Decimal("0.00")

            first_movements = verify.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.reference_type == "withdrawal",
                    WalletTransaction.reference_id == __import__("uuid").UUID(first_id),
                )
            ).all()
            assert {item.type for item in first_movements} == {"hold", "debit"}

            second_movements = verify.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.reference_type == "withdrawal",
                    WalletTransaction.reference_id == __import__("uuid").UUID(second_id),
                )
            ).all()
            assert {item.type for item in second_movements} == {"hold", "release"}

            assert verify.scalar(
                select(AuditLog).where(
                    AuditLog.entity_type == "withdrawal",
                    AuditLog.entity_id == __import__("uuid").UUID(first_id),
                    AuditLog.action == "withdrawal.paid",
                )
            ) is not None
        finally:
            verify.close()

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()


def test_withdrawal_endpoints_require_authentication():
    with TestClient(app) as client:
        response = client.get("/api/wallet/me/withdrawals")
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"
