"""Profile, address, notification, and support schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = None


class AddressCreate(BaseModel):
    label: str = "Home"
    full_name: str
    phone: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "India"
    is_default: bool = False


class AddressOut(AddressCreate):
    id: int

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: int
    title: str
    body: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=5)
    order_id: Optional[int] = None


class SupportTicketReply(BaseModel):
    admin_reply: str
    status: str = "resolved"


class SupportTicketOut(BaseModel):
    id: int
    user_id: int
    subject: str
    message: str
    status: str
    admin_reply: Optional[str] = None
    order_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
