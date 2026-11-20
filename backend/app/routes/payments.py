"""M-Pesa checkout, callback and respondent payment history endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.schemas.payments import (
    CheckoutResponse,
    MpesaCheckoutCreate,
    PaymentPage,
    PaymentPublic,
)
from app.security.dependencies import get_current_user
from app.services.payments import (
    create_checkout,
    list_user_payments,
    process_mpesa_callback,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post(
    "/mpesa/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def mpesa_checkout(
    data: MpesaCheckoutCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        payment = create_checkout(
            db, user.id, data.plan_id, data.phone_number, idempotency_key
        )
        message = (
            "STK Push initiated. Complete the prompt on your phone."
            if payment.checkout_request_id
            else (
                "The payment request status is uncertain. Do not start another "
                "checkout; check your payment status or contact support."
            )
        )
        return CheckoutResponse(payment=payment, message=message)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/me", response_model=PaymentPage)
def my_payments(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = list_user_payments(db, user.id, limit, offset)
    return PaymentPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{payment_id}", response_model=PaymentPublic)
def payment_details(
    payment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.payments import Payment

    payment = db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return payment


@router.post("/mpesa/callback")
async def mpesa_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
        process_mpesa_callback(db, payload)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Payment callback could not yet be verified.",
        ) from exc
