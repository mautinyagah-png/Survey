"""Administrator-only payment records listing."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.models.payments import Payment
from app.schemas.payments import AdminPaymentPage, AdminPaymentPublic
from app.security.dependencies import get_admin_user

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])


@router.get("", response_model=AdminPaymentPage)
def list_all_payments(
    status_filter: Literal["pending", "completed", "failed", "cancelled"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    filters = []
    if status_filter:
        filters.append(Payment.status == status_filter)

    count_query = select(func.count(Payment.id))
    query = select(Payment, User.email, User.full_name).join(
        User, User.id == Payment.user_id
    )
    if filters:
        count_query = count_query.where(*filters)
        query = query.where(*filters)

    total = db.scalar(count_query) or 0
    rows = db.execute(
        query.order_by(Payment.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = [
        AdminPaymentPublic(
            id=payment.id,
            plan_id=payment.plan_id,
            amount=payment.amount,
            currency=payment.currency,
            phone_number_masked=payment.phone_number_masked,
            provider=payment.provider,
            status=payment.status,
            mpesa_receipt_number=payment.mpesa_receipt_number,
            result_description=payment.result_description,
            created_at=payment.created_at,
            completed_at=payment.completed_at,
            user_email=email,
            user_full_name=full_name,
        )
        for payment, email, full_name in rows
    ]
    return AdminPaymentPage(items=items, total=total, limit=limit, offset=offset)
