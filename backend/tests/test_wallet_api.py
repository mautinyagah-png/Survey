from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.identity import Role, User
from app.models.rewards import Wallet, WalletTransaction
from app.security.dependencies import get_current_user


def test_wallet_endpoints_only_return_authenticated_users_records():
    connection = engine.connect()
    transaction = connection.begin()

    try:
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        role = db.scalar(
            select(Role).where(Role.name == "respondent")
        )
        assert role is not None

        now = datetime.now(timezone.utc)

        user = User(
            id=uuid4(),
            email=f"wallet-api-{uuid4()}@example.com",
            full_name="Wallet API Test Respondent",
            password_hash="test-only",
            role_id=role.id,
            status="active",
            email_verified_at=now,
        )

        other_user = User(
            id=uuid4(),
            email=f"wallet-other-{uuid4()}@example.com",
            full_name="Other Wallet Respondent",
            password_hash="test-only",
            role_id=role.id,
            status="active",
            email_verified_at=now,
        )

        db.add_all([user, other_user])
        db.flush()

        own_wallet = Wallet(
            user_id=user.id,
            currency="KES",
            pending_balance=Decimal("40.00"),
            available_balance=Decimal("15.00"),
            total_earned=Decimal("15.00"),
        )

        other_wallet = Wallet(
            user_id=other_user.id,
            currency="KES",
            pending_balance=Decimal("999.00"),
            available_balance=Decimal("999.00"),
            total_earned=Decimal("999.00"),
        )

        db.add_all([own_wallet, other_wallet])
        db.flush()

        older_transaction = WalletTransaction(
            user_id=user.id,
            type="pending_credit",
            amount=Decimal("25.00"),
            currency="KES",
            reference_type="reward",
            reference_id=uuid4(),
            description="Older pending reward",
            created_at=now - timedelta(minutes=5),
        )

        newer_transaction = WalletTransaction(
            user_id=user.id,
            type="pending_credit",
            amount=Decimal("15.00"),
            currency="KES",
            reference_type="reward",
            reference_id=uuid4(),
            description="Newer pending reward",
            created_at=now,
        )

        other_transaction = WalletTransaction(
            user_id=other_user.id,
            type="credit",
            amount=Decimal("999.00"),
            currency="KES",
            description="Private transaction belonging to another user",
        )

        db.add_all([
            older_transaction,
            newer_transaction,
            other_transaction,
        ])
        db.commit()

        user_id = user.id
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

        client = TestClient(app)

        # Verify wallet balances.
        response = client.get("/api/wallet/me")
        assert response.status_code == 200, response.text

        wallets = response.json()
        assert len(wallets) == 1
        assert wallets[0]["currency"].strip() == "KES"
        assert wallets[0]["pending_balance"] == "40.00"
        assert wallets[0]["available_balance"] == "15.00"
        assert wallets[0]["total_earned"] == "15.00"

        # Verify transaction history and ownership isolation.
        response = client.get("/api/wallet/me/transactions")
        assert response.status_code == 200, response.text

        history = response.json()
        assert history["total"] == 2
        assert len(history["items"]) == 2
        assert history["items"][0]["description"] == "Newer pending reward"
        assert history["items"][1]["description"] == "Older pending reward"
        assert all(
            item["amount"] != "999.00"
            for item in history["items"]
        )

        # Verify pagination.
        response = client.get(
            "/api/wallet/me/transactions?limit=1&offset=0"
        )
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["total"] == 2
        assert page["limit"] == 1
        assert page["offset"] == 0
        assert len(page["items"]) == 1
        assert page["items"][0]["description"] == "Newer pending reward"

        # Invalid pagination must be rejected.
        response = client.get(
            "/api/wallet/me/transactions?limit=101"
        )
        assert response.status_code == 422

        print("PASS: Authenticated respondent can retrieve wallet balances.")
        print("PASS: Wallet balances are returned separately by currency.")
        print("PASS: Transaction history is newest first.")
        print("PASS: Another respondent's wallet and transactions are hidden.")
        print("PASS: Transaction pagination works.")
        print("PASS: Invalid pagination parameters are rejected.")

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()
        print("Temporary wallet API test data rolled back.")


def test_wallet_endpoints_require_authentication():
    """Anonymous visitors must not access wallet balances or transactions."""

    with TestClient(app) as client:
        for path in (
            "/api/wallet/me",
            "/api/wallet/me/transactions",
        ):
            response = client.get(path)

            assert response.status_code == 401, (
                f"{path} should reject anonymous access, "
                f"got {response.status_code}: {response.text}"
            )
            assert response.headers.get("www-authenticate") == "Bearer"

    print("PASS: Anonymous wallet balance access is rejected.")
    print("PASS: Anonymous transaction history access is rejected.")
