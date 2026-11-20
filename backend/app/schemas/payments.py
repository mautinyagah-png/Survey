"""Public schemas for subscription payments."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MpesaCheckoutCreate(BaseModel):
    plan_id: int = Field(gt=0)
    phone_number: str = Field(min_length=9, max_length=16)


class PaymentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: int
    amount: Decimal
    currency: str
    phone_number_masked: str
    provider: str
    status: str
    mpesa_receipt_number: str | None
    result_description: str | None
    created_at: datetime
    completed_at: datetime | None


class PaymentPage(BaseModel):
    items: list[PaymentPublic]
    total: int
    limit: int
    offset: int


class CheckoutResponse(BaseModel):
    payment: PaymentPublic
    message: str


class AdminPaymentPublic(PaymentPublic):
    user_email: str | None = None
    user_full_name: str | None = None


class AdminPaymentPage(BaseModel):
    items: list[AdminPaymentPublic]
    total: int
    limit: int
    offset: int
