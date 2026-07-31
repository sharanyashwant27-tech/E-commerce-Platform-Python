"""Rewrite imports after folder restructure."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS = [
    ("from config.settings import settings", "from config.settings import settings"),
    ("from config.settings import get_settings", "from config.settings import get_settings"),
    ("from auth.security import", "from auth.security import"),
    ("from utils.exceptions import", "from utils.exceptions import"),
    ("from utils.logging import", "from utils.logging import"),
    ("from utils.enums import", "from utils.enums import"),
    ("from utils.enums import", "from utils.enums import"),
    ("from models.entities import", "from models.entities import"),
    ("from models.session import", "from models.session import"),
    ("from models import", "from models import"),
    ("from schemas.auth import", "from schemas.auth import"),
    ("from schemas.account import", "from schemas.account import"),
    ("from schemas.cart import", "from schemas.cart import"),
    ("from schemas.order import", "from schemas.order import"),
    ("from schemas.product import", "from schemas.product import"),
    ("from auth.deps import", "from auth.deps import"),
    ("from auth.deps import", "from auth.deps import"),
    ("from services.auth_service import", "from services.auth_service import"),
    ("from services.account_service import", "from services.account_service import"),
    ("from services.cart_service import", "from services.cart_service import"),
    ("from services.discount_service import", "from services.discount_service import"),
    ("from services.order_service import", "from services.order_service import"),
    ("from services.product_service import", "from services.product_service import"),
    ("from utils.email import", "from utils.email import"),
    ("from utils.payment import", "from utils.payment import"),
    ("from utils.cache import", "from utils.cache import"),
    ("from utils.cache import", "from utils.cache import"),
    ("from utils.invoice import", "from utils.invoice import"),
    ("from app.workers.tasks import", "from app.workers.tasks import"),
    ("from app.workers.celery_app import", "from app.workers.celery_app import"),
    ("from main import app", "from main import app"),
    ("import models.entities", "import models.entities"),
    ("from api import api_router", "from api import api_router"),
    ("from api.web import router as web_router", "from api.web import router as web_router"),
    ('Path(__file__).resolve().parents[1] / "templates"', 'Path(__file__).resolve().parents[1] / "templates"'),
    ("config.settings", "config.settings"),
]


def rewrite(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for folder in [
        "api",
        "auth",
        "models",
        "schemas",
        "services",
        "repository",
        "middleware",
        "utils",
        "config",
        "migrations",
        "tests",
        "scripts",
        "app",
    ]:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            if rewrite(path):
                changed += 1
                print("updated", path.relative_to(ROOT))
    print(f"Done. Updated {changed} files.")


if __name__ == "__main__":
    main()
