"""Local product image uploads (S3-ready interface)."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import require_roles
from config.settings import settings
from utils.exceptions import ValidationError
from utils.enums import UserRole
from models.entities import User
from models.session import get_db

router = APIRouter()

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.post("/images")
async def upload_image(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER, UserRole.ADMIN))],
    file: UploadFile = File(...),
):
    _ = db, user
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise ValidationError(f"Unsupported image type. Allowed: {', '.join(ALLOWED)}")
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationError(f"File exceeds {settings.max_upload_size_mb}MB")

    dest_dir = Path(settings.upload_dir) / "products"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    path = dest_dir / name
    path.write_bytes(content)
    url = f"/uploads/products/{name}"
    return {"url": url, "filename": name}
