"""Safaricom Daraja STK Push and verified subscription payment processing."""

import base64
import re
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.administration import AuditLog
from app.models.payments import Payment
from app.models.identity import User
from app.models.subscriptions import SubscriptionPlan, UserSubscription


class DarajaRejectedError(ValueError):
    """Daraja explicitly rejected an STK Push request."""


def _phone_cipher():
    key = get_settings().mpesa_encryption_key
    if not key:
        raise RuntimeError("MPESA_ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("MPESA_ENCRYPTION_KEY is invalid.") from exc


def _encrypt_phone(phone: str) -> str:
    return _phone_cipher().encrypt(phone.encode()).decode()


def _decrypt_phone(encrypted_phone: str) -> str:
    try:
        return _phone_cipher().decrypt(encrypted_phone.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Stored payment phone number could not be verified.") from exc


def normalize_phone(value: str) -> str:
    """Normalize Kenyan mobile numbers to the Daraja 254XXXXXXXXX format."""
    digits = re.sub(r"\D", "", value)

    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        if len(digits) == 9:
            digits = "254" + digits

    if not re.fullmatch(r"254[17]\d{8}", digits):
        raise ValueError("Enter a valid Kenyan Safaricom mobile number.")

    return digits


def mask_phone(phone: str) -> str:
    return phone[:6] + "****" + phone[-2:]




def _audit_payment(
    db: Session,
    payment: Payment,
    action: str,
    actor_id=None,
    metadata: dict | None = None,
):
    """Record payment events without exposing the customer's full phone number."""
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type="payment",
            entity_id=payment.id,
            metadata_json=metadata or {},
        )
    )


def _daraja_config():
    settings = get_settings()

    if settings.mpesa_environment not in {"sandbox", "production"}:
        raise ValueError("M-Pesa environment must be sandbox or production.")

    required = (
        settings.mpesa_consumer_key,
        settings.mpesa_consumer_secret,
        settings.mpesa_shortcode,
        settings.mpesa_passkey,
        settings.mpesa_callback_url,
    )
    if not all(required):
        raise ValueError("M-Pesa checkout is not configured yet.")

    if not settings.mpesa_callback_url.startswith("https://"):
        raise ValueError("M-Pesa callback URL must use HTTPS.")

    base = (
        "https://sandbox.safaricom.co.ke"
        if settings.mpesa_environment == "sandbox"
        else "https://api.safaricom.co.ke"
    )
    return settings, base


def _access_token(settings, base: str) -> str:
    response = httpx.get(
        f"{base}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(settings.mpesa_consumer_key, settings.mpesa_consumer_secret),
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise ValueError("Daraja did not return an access token.")
    return token


def _timestamp() -> str:
    return datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")


def _password(shortcode: str, passkey: str, timestamp: str) -> str:
    raw = f"{shortcode}{passkey}{timestamp}".encode()
    return base64.b64encode(raw).decode()


def _stk_push(settings, base: str, phone: str, amount: int, account: str):
    token = _access_token(settings, base)
    timestamp = _timestamp()

    payload = {
        "BusinessShortCode": settings.mpesa_shortcode,
        "Password": _password(
            settings.mpesa_shortcode, settings.mpesa_passkey, timestamp
        ),
        "Timestamp": timestamp,
        "TransactionType": settings.mpesa_transaction_type,
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.mpesa_shortcode,
        "PhoneNumber": phone,
        "CallBackURL": settings.mpesa_callback_url,
        "AccountReference": account[:12],
        "TransactionDesc": "SurveyKE subscription",
    }

    response = httpx.post(
        f"{base}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if str(data.get("ResponseCode")) != "0":
        raise DarajaRejectedError(data.get("ResponseDescription") or "STK Push was rejected.")

    if not data.get("CheckoutRequestID") or not data.get("MerchantRequestID"):
        raise ValueError("Daraja returned an incomplete STK Push response.")

    return data


def _query_stk(settings, base: str, checkout_request_id: str):
    token = _access_token(settings, base)
    timestamp = _timestamp()

    payload = {
        "BusinessShortCode": settings.mpesa_shortcode,
        "Password": _password(
            settings.mpesa_shortcode, settings.mpesa_passkey, timestamp
        ),
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    response = httpx.post(
        f"{base}/mpesa/stkpushquery/v1/query",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def create_checkout(
    db: Session,
    user_id,
    plan_id: int,
    phone_number: str,
    idempotency_key: str,
) -> Payment:
    """Create a pending payment and request an STK Push exactly once per key."""
    settings, base = _daraja_config()
    phone = normalize_phone(phone_number)

    if not re.fullmatch(r"[A-Za-z0-9._:-]{16,128}", idempotency_key or ""):
        raise ValueError("A valid checkout idempotency key is required.")

    # Serialize checkout attempts for this user. This prevents two concurrent
    # requests with the same key from both initiating an STK Push.
    locked_user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if locked_user is None:
        raise ValueError("The checkout user could not be found.")

    existing = db.scalar(
        select(Payment).where(
            Payment.user_id == user_id,
            Payment.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.plan_id != plan_id or _decrypt_phone(existing.phone_number_encrypted) != phone:
            raise ValueError(
                "This checkout key has already been used with different details. "
                "Generate a new key for a new payment attempt."
            )
        return existing

    plan = db.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.is_active.is_(True),
        )
    )
    if plan is None:
        raise ValueError("The selected subscription plan is unavailable.")

    if plan.price_amount is None or Decimal(plan.price_amount) <= 0:
        raise ValueError("This subscription plan does not have a payment price configured.")

    amount = Decimal(plan.price_amount)
    if plan.currency != "KES":
        raise ValueError("M-Pesa subscription payments currently support KES only.")

    if amount != amount.to_integral_value():
        raise ValueError("M-Pesa subscription prices must be whole Kenyan shillings.")

    subscription = UserSubscription(
        user_id=user_id,
        plan_id=plan.id,
        status="pending",
        payment_provider="mpesa",
    )
    db.add(subscription)
    db.flush()

    payment = Payment(
        user_id=user_id,
        plan_id=plan.id,
        subscription_id=subscription.id,
        provider="mpesa",
        amount=amount,
        currency="KES",
        phone_number_encrypted=_encrypt_phone(phone),
        phone_number_masked=mask_phone(phone),
        idempotency_key=idempotency_key,
        status="pending",
    )
    db.add(payment)
    db.flush()
    _audit_payment(
        db,
        payment,
        "payment.checkout_requested",
        actor_id=user_id,
        metadata={
            "plan_id": plan.id,
            "amount": str(amount),
            "currency": "KES",
            "provider": "mpesa",
        },
    )
    db.commit()
    db.refresh(payment)

    try:
        response = _stk_push(
            settings,
            base,
            phone,
            int(amount),
            f"SK{str(payment.id).replace('-', '')[:10]}",
        )
        payment.merchant_request_id = response["MerchantRequestID"]
        payment.checkout_request_id = response["CheckoutRequestID"]
        payment.result_description = response.get("CustomerMessage")
        _audit_payment(
            db,
            payment,
            "payment.stk_push_accepted",
            actor_id=user_id,
            metadata={"status": "pending", "provider": "mpesa"},
        )
        db.commit()
        db.refresh(payment)
        return payment

    except Exception as exc:
        db.rollback()
        current = db.get(Payment, payment.id)

        if current is not None and current.status == "pending":
            definitive_rejection = isinstance(exc, DarajaRejectedError) or (
                isinstance(exc, httpx.HTTPStatusError)
                and 400 <= exc.response.status_code < 500
            )

            if definitive_rejection:
                current.status = "failed"
                current.result_description = "M-Pesa rejected the payment request."
                pending_subscription = db.get(
                    UserSubscription, current.subscription_id
                )
                if pending_subscription is not None:
                    pending_subscription.status = "failed"

                _audit_payment(
                    db,
                    current,
                    "payment.stk_push_rejected",
                    actor_id=user_id,
                    metadata={"status": "failed", "provider": "mpesa"},
                )
                db.commit()

                raise ValueError(
                    "M-Pesa rejected the payment request. Please try again."
                ) from exc

            # A timeout, connection failure, server error or unexpected response
            # may happen after Daraja has received the request. Do not mark it
            # failed and do not create a second STK request with this key.
            current.result_description = (
                "M-Pesa request outcome is uncertain. Do not start another "
                "checkout; check payment status or contact support."
            )
            _audit_payment(
                db,
                current,
                "payment.stk_push_uncertain",
                actor_id=user_id,
                metadata={"status": "pending", "provider": "mpesa"},
            )
            db.commit()
            db.refresh(current)
            return current

        raise


def _callback_metadata(callback: dict) -> dict:
    result = {}
    metadata = callback.get("CallbackMetadata") or {}
    for item in metadata.get("Item", []):
        if isinstance(item, dict) and "Name" in item:
            result[item["Name"]] = item.get("Value")
    return result


def process_mpesa_callback(db: Session, payload: dict) -> None:
    """Verify the callback with Daraja before activating a subscription."""
    body = payload.get("Body") or {}
    callback = body.get("stkCallback") or {}

    checkout_id = callback.get("CheckoutRequestID")
    if not checkout_id:
        raise ValueError("Callback is missing its checkout reference.")

    payment = db.scalar(
        select(Payment)
        .where(Payment.checkout_request_id == checkout_id)
        .with_for_update()
    )
    if payment is None:
        raise ValueError("Payment reference was not found.")

    merchant_id = callback.get("MerchantRequestID")
    if (
        not merchant_id
        or not payment.merchant_request_id
        or str(merchant_id) != str(payment.merchant_request_id)
    ):
        raise ValueError("Callback merchant reference does not match the payment.")

    if payment.status == "completed":
        return

    result_code = str(callback.get("ResultCode", ""))

    # Never trust the callback result alone, including failure callbacks.
    settings, base = _daraja_config()
    query_result = _query_stk(settings, base, checkout_id)
    verified_result_code = str(query_result.get("ResultCode", ""))

    if not verified_result_code or verified_result_code != result_code:
        raise ValueError("Callback result does not match Daraja's payment query.")

    payment.result_code = verified_result_code
    payment.result_description = str(callback.get("ResultDesc", ""))[:500]

    if verified_result_code != "0":
        payment.status = "failed"
        subscription = db.get(UserSubscription, payment.subscription_id)
        if subscription is not None and subscription.status == "pending":
            subscription.status = "failed"
        _audit_payment(
            db,
            payment,
            "payment.verified_failure",
            metadata={
                "result_code": verified_result_code,
                "status": "failed",
                "provider": "mpesa",
            },
        )
        db.commit()
        return

    metadata = _callback_metadata(callback)
    receipt = metadata.get("MpesaReceiptNumber")
    callback_amount = metadata.get("Amount")
    callback_phone = metadata.get("PhoneNumber")

    if not receipt or callback_amount is None or callback_phone is None:
        raise ValueError("Successful callback is missing required payment details.")

    if Decimal(str(callback_amount)) != payment.amount:
        raise ValueError("Callback amount does not match the expected payment.")

    if normalize_phone(str(callback_phone)) != _decrypt_phone(payment.phone_number_encrypted):
        raise ValueError("Callback phone number does not match the payment.")

    # The unique receipt constraint prevents a receipt being reused.
    payment.mpesa_receipt_number = str(receipt)
    payment.status = "completed"
    payment.completed_at = datetime.now(ZoneInfo("UTC"))

    subscription = db.get(UserSubscription, payment.subscription_id)
    if subscription is None:
        raise ValueError("The pending subscription could not be found.")

    if subscription.status != "pending":
        raise ValueError("The subscription is no longer pending.")

    now = datetime.now(ZoneInfo("UTC"))
    plan = db.get(SubscriptionPlan, payment.plan_id)
    if plan is None:
        raise ValueError("The subscription plan no longer exists.")

    periods = {
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30),
        "quarterly": timedelta(days=90),
        "yearly": timedelta(days=365),
        "annual": timedelta(days=365),
    }
    duration = periods.get(plan.billing_period.lower())
    if duration is None:
        raise ValueError("Unsupported subscription billing period.")

    subscription.status = "active"
    subscription.starts_at = now
    subscription.ends_at = now + duration
    subscription.payment_provider = "mpesa"
    subscription.payment_reference = f"MPESA-{receipt}"

    _audit_payment(
        db,
        payment,
        "payment.verified_success",
        metadata={
            "plan_id": payment.plan_id,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "provider": "mpesa",
            "status": "completed",
        },
    )
    db.commit()


def list_user_payments(db: Session, user_id, limit: int, offset: int):
    query = select(Payment).where(Payment.user_id == user_id)
    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0
    items = db.scalars(
        query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return items, total
