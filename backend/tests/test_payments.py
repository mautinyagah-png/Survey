from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.identity import Role, User
from app.models.payments import Payment
from app.models.subscriptions import SubscriptionPlan, UserSubscription
from app.services import payments as payment_service


def create_payment_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    role = db.scalar(select(Role).where(Role.name == "respondent"))
    plan = db.scalar(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.tier_rank)
        .limit(1)
    )

    assert role is not None
    assert plan is not None

    user = User(
        id=uuid4(),
        email=f"payment-test-{uuid4()}@example.com",
        full_name="Payment Test User",
        password_hash="test-only",
        role_id=role.id,
        status="active",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status="pending",
        payment_provider="mpesa",
    )
    db.add(subscription)
    db.flush()

    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        subscription_id=subscription.id,
        provider="mpesa",
        amount=Decimal("100.00"),
        currency="KES",
        phone_number_encrypted=payment_service._encrypt_phone("254712345678"),
        phone_number_masked="254712****78",
        idempotency_key="test-idempotency-key-0001",
        checkout_request_id=f"ws_CO_{uuid4().hex}",
        merchant_request_id="merchant-test",
        status="pending",
    )
    db.add(payment)
    db.commit()

    return connection, transaction, db, payment.id, subscription.id, payment.checkout_request_id


def callback_payload(checkout_id, result_code="0"):
    callback = {
        "MerchantRequestID": "merchant-test",
        "CheckoutRequestID": checkout_id,
        "ResultCode": int(result_code),
        "ResultDesc": "Test payment result",
    }

    if result_code == "0":
        callback["CallbackMetadata"] = {
            "Item": [
                {"Name": "Amount", "Value": 100},
                {"Name": "MpesaReceiptNumber", "Value": f"TEST{uuid4().hex[:8]}"},
                {"Name": "PhoneNumber", "Value": 254712345678},
            ]
        }

    return {"Body": {"stkCallback": callback}}



def test_payment_phone_is_encrypted_at_rest():
    encrypted = payment_service._encrypt_phone("254712345678")
    assert encrypted != "254712345678"
    assert payment_service._decrypt_phone(encrypted) == "254712345678"


def test_phone_number_normalization():
    assert payment_service.normalize_phone("0712345678") == "254712345678"
    assert payment_service.normalize_phone("+254712345678") == "254712345678"
    assert payment_service.normalize_phone("254712345678") == "254712345678"

    with pytest.raises(ValueError):
        payment_service.normalize_phone("12345")


def test_verified_success_activates_subscription_and_duplicate_is_safe(monkeypatch):
    connection, transaction, db, payment_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )

    query_calls = []

    def fake_query(settings, base, reference):
        query_calls.append(reference)
        return {"ResultCode": "0"}

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )
    monkeypatch.setattr(payment_service, "_query_stk", fake_query)

    try:
        payload = callback_payload(checkout_id)

        payment_service.process_mpesa_callback(db, payload)

        payment = db.get(Payment, payment_id)
        subscription = db.get(UserSubscription, subscription_id)

        assert payment.status == "completed"
        assert payment.mpesa_receipt_number.startswith("TEST")
        assert payment.completed_at is not None
        assert subscription.status == "active"
        assert subscription.starts_at is not None
        assert subscription.ends_at is not None
        assert len(query_calls) == 1

        # A duplicate callback must not query or activate the subscription twice.
        payment_service.process_mpesa_callback(db, payload)
        assert len(query_calls) == 1
        assert subscription.status == "active"

    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_verified_failure_does_not_activate_subscription(monkeypatch):
    connection, transaction, db, payment_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )
    monkeypatch.setattr(
        payment_service,
        "_query_stk",
        lambda settings, base, reference: {"ResultCode": "1032"},
    )

    try:
        payment_service.process_mpesa_callback(
            db, callback_payload(checkout_id, result_code="1032")
        )

        payment = db.get(Payment, payment_id)
        subscription = db.get(UserSubscription, subscription_id)

        assert payment.status == "failed"
        assert subscription.status == "failed"
        assert subscription.starts_at is None

    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_mismatched_callback_cannot_change_payment(monkeypatch):
    connection, transaction, db, payment_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )
    monkeypatch.setattr(
        payment_service,
        "_query_stk",
        lambda settings, base, reference: {"ResultCode": "1032"},
    )

    try:
        with pytest.raises(ValueError):
            payment_service.process_mpesa_callback(
                db, callback_payload(checkout_id, result_code="0")
            )

        db.expire_all()
        payment = db.get(Payment, payment_id)
        subscription = db.get(UserSubscription, subscription_id)

        assert payment.status == "pending"
        assert subscription.status == "pending"

    finally:
        db.close()
        transaction.rollback()
        connection.close()



def test_checkout_idempotency_returns_existing_payment(monkeypatch):
    connection, transaction, db, payment_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )

    payment = db.get(Payment, payment_id)

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )

    def unexpected_stk(*args, **kwargs):
        raise AssertionError("Duplicate checkout must not initiate another STK Push.")

    monkeypatch.setattr(payment_service, "_stk_push", unexpected_stk)

    try:
        existing = payment_service.create_checkout(
            db,
            payment.user_id,
            payment.plan_id,
            "0712345678",
            "test-idempotency-key-0001",
        )

        assert existing.id == payment_id
        assert existing.checkout_request_id == checkout_id

        with pytest.raises(ValueError, match="different details"):
            payment_service.create_checkout(
                db,
                payment.user_id,
                payment.plan_id,
                "0711111111",
                "test-idempotency-key-0001",
            )

    finally:
        db.close()
        transaction.rollback()
        connection.close()



def test_checkout_timeout_keeps_payment_pending_and_reuses_key(monkeypatch):
    connection, transaction, db, original_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )
    original = db.get(Payment, original_id)
    plan = db.get(SubscriptionPlan, original.plan_id)
    plan.price_amount = Decimal("100.00")
    db.flush()

    calls = []

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )

    def timeout_stk(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("Simulated response timeout")

    monkeypatch.setattr(payment_service, "_stk_push", timeout_stk)

    key = "timeout-idempotency-key-0001"

    try:
        uncertain = payment_service.create_checkout(
            db,
            original.user_id,
            original.plan_id,
            "0712345678",
            key,
        )

        assert uncertain.status == "pending"
        assert uncertain.checkout_request_id is None
        assert "uncertain" in uncertain.result_description.lower()

        uncertain_subscription = db.get(
            UserSubscription, uncertain.subscription_id
        )
        assert uncertain_subscription.status == "pending"

        # Retrying with the same key must return the original record and
        # must never issue another STK Push.
        repeated = payment_service.create_checkout(
            db,
            original.user_id,
            original.plan_id,
            "0712345678",
            key,
        )

        assert repeated.id == uncertain.id
        assert len(calls) == 1

    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_mismatched_merchant_reference_cannot_change_payment(monkeypatch):
    connection, transaction, db, payment_id, subscription_id, checkout_id = (
        create_payment_fixture()
    )

    monkeypatch.setattr(
        payment_service,
        "_daraja_config",
        lambda: (object(), "https://sandbox.example"),
    )
    monkeypatch.setattr(
        payment_service,
        "_query_stk",
        lambda settings, base, reference: {"ResultCode": "0"},
    )

    try:
        payload = callback_payload(checkout_id)
        payload["Body"]["stkCallback"]["MerchantRequestID"] = "wrong-merchant"

        with pytest.raises(ValueError, match="merchant reference"):
            payment_service.process_mpesa_callback(db, payload)

        db.expire_all()
        assert db.get(Payment, payment_id).status == "pending"
        assert db.get(UserSubscription, subscription_id).status == "pending"
    finally:
        db.close()
        transaction.rollback()
        connection.close()

