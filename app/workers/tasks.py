"""Background tasks for email and notifications."""

import logging

from utils.email import send_email
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="send_email_task", bind=True, max_retries=3)
def send_email_task(self, to_email: str, subject: str, html_body: str) -> bool:
    try:
        return send_email(to_email, subject, html_body)
    except Exception as exc:
        logger.exception("Email task failed")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="notify_order_status")
def notify_order_status(to_email: str, order_number: str, status: str) -> bool:
    html = (
        f"<p>Your order <strong>{order_number}</strong> status is now "
        f"<strong>{status}</strong>.</p>"
        f"<p>Thank you for shopping with ShopSphere.</p>"
    )
    return send_email(to_email, f"Order {order_number} update", html)
