"""Profile, addresses, notifications, and support tickets."""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.exceptions import ForbiddenError, NotFoundError
from models.entities import Address, Notification, SupportTicket, User


class AccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_profile(self, user: User, full_name: Optional[str], phone: Optional[str]) -> User:
        if full_name is not None:
            user.full_name = full_name
        if phone is not None:
            user.phone = phone
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def list_addresses(self, user: User) -> Sequence[Address]:
        result = await self.db.execute(
            select(Address).where(Address.user_id == user.id).order_by(Address.is_default.desc())
        )
        return result.scalars().all()

    async def create_address(self, user: User, data: dict) -> Address:
        if data.get("is_default"):
            existing = await self.list_addresses(user)
            for addr in existing:
                addr.is_default = False
        addr = Address(user_id=user.id, **data)
        self.db.add(addr)
        await self.db.flush()
        await self.db.refresh(addr)
        return addr

    async def delete_address(self, user: User, address_id: int) -> None:
        addr = await self.db.get(Address, address_id)
        if not addr or addr.user_id != user.id:
            raise NotFoundError("Address not found")
        await self.db.delete(addr)
        await self.db.flush()

    async def notify(
        self, user_id: int, title: str, body: str, link: Optional[str] = None
    ) -> Notification:
        note = Notification(user_id=user_id, title=title, body=body, link=link)
        self.db.add(note)
        await self.db.flush()
        return note

    async def list_notifications(self, user: User, unread_only: bool = False) -> Sequence[Notification]:
        q = select(Notification).where(Notification.user_id == user.id)
        if unread_only:
            q = q.where(Notification.is_read.is_(False))
        q = q.order_by(Notification.created_at.desc()).limit(50)
        return (await self.db.execute(q)).scalars().all()

    async def mark_read(self, user: User, notification_id: int) -> Notification:
        note = await self.db.get(Notification, notification_id)
        if not note or note.user_id != user.id:
            raise NotFoundError("Notification not found")
        note.is_read = True
        await self.db.flush()
        return note

    async def create_ticket(self, user: User, subject: str, message: str, order_id: Optional[int]) -> SupportTicket:
        ticket = SupportTicket(
            user_id=user.id, subject=subject, message=message, order_id=order_id, status="open"
        )
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def list_tickets(self, user: User, all_tickets: bool = False) -> Sequence[SupportTicket]:
        q = select(SupportTicket).order_by(SupportTicket.created_at.desc())
        if not all_tickets:
            q = q.where(SupportTicket.user_id == user.id)
        return (await self.db.execute(q)).scalars().all()

    async def reply_ticket(self, ticket_id: int, admin_reply: str, status: str) -> SupportTicket:
        ticket = await self.db.get(SupportTicket, ticket_id)
        if not ticket:
            raise NotFoundError("Ticket not found")
        ticket.admin_reply = admin_reply
        ticket.status = status
        await self.db.flush()
        await self.notify(
            ticket.user_id,
            "Support reply",
            f"Your ticket '{ticket.subject}' was updated to {status}.",
            link="/support",
        )
        return ticket
