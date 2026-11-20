from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

class AdminUserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: str
    status: str
    preferred_currency: str
    email_verified_at: datetime | None
    created_at: datetime
    last_login_at: datetime | None

class AdminUserPage(BaseModel):
    items: list[AdminUserPublic]
    total: int
    limit: int
    offset: int

class AdminUserStatusUpdate(BaseModel):
    status: Literal["active", "suspended"]
