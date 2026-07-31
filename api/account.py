"""Profile, addresses, notifications, support."""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user, require_roles
from schemas.account import (
    AddressCreate,
    AddressOut,
    NotificationOut,
    ProfileUpdate,
    SupportTicketCreate,
    SupportTicketOut,
    SupportTicketReply,
)
from schemas.auth import MessageOut, UserOut
from services.account_service import AccountService
from utils.enums import UserRole
from models.entities import User
from models.session import get_db

router = APIRouter()


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    payload: ProfileUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).update_profile(user, payload.full_name, payload.phone)


@router.get("/addresses", response_model=List[AddressOut])
async def list_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).list_addresses(user)


@router.post("/addresses", response_model=AddressOut, status_code=201)
async def create_address(
    payload: AddressCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).create_address(user, payload.model_dump())


@router.delete("/addresses/{address_id}", response_model=MessageOut)
async def delete_address(
    address_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    await AccountService(db).delete_address(user, address_id)
    return MessageOut(message="Address deleted")


@router.get("/notifications", response_model=List[NotificationOut])
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    unread_only: bool = Query(False),
):
    return await AccountService(db).list_notifications(user, unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).mark_read(user, notification_id)


@router.post("/support", response_model=SupportTicketOut, status_code=201)
async def create_ticket(
    payload: SupportTicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).create_ticket(
        user, payload.subject, payload.message, payload.order_id
    )


@router.get("/support", response_model=List[SupportTicketOut])
async def my_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await AccountService(db).list_tickets(user)


@router.get("/support/all", response_model=List[SupportTicketOut])
async def all_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return await AccountService(db).list_tickets(user, all_tickets=True)


@router.post("/support/{ticket_id}/reply", response_model=SupportTicketOut)
async def reply_ticket(
    ticket_id: int,
    payload: SupportTicketReply,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return await AccountService(db).reply_ticket(ticket_id, payload.admin_reply, payload.status)
