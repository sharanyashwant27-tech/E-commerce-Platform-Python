"""ShopSphere FastAPI entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import api_router
from api.web import router as web_router
from app import __version__
from config.settings import settings
from middleware import register_exception_handlers
from models.session import Base, engine
import models.entities  # noqa: F401 — register metadata
from utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    upload = Path(settings.upload_dir) / "products"
    upload.mkdir(parents=True, exist_ok=True)
    (Path(settings.upload_dir) / "invoices").mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("%s v%s starting on port %s", settings.app_name, __version__, settings.port)
    yield
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Production-ready Amazon/Flipkart-style E-commerce Platform. "
        "Clean Architecture · JWT/OAuth2 · RBAC · Stripe/Razorpay sandbox."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

uploads_dir = Path(settings.upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(web_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.app_name, "version": __version__}


def run():
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug and not settings.is_production,
    )


if __name__ == "__main__":
    run()
