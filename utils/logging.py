"""Structured application logging configuration."""

import logging
import sys
from typing import Optional

from config.settings import settings


def setup_logging(level: Optional[str] = None) -> None:
    log_level = level or ("DEBUG" if settings.debug else "INFO")
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        if settings.debug
        else "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if not settings.debug else logging.INFO
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
