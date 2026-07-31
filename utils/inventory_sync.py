"""Real-time inventory fan-out via Redis pub/sub + in-process subscribers.

Postgres remains the source of truth. After stock mutations we:
1. Cache the latest snapshot in Redis (best-effort)
2. PUBLISH on channel ``shopsphere:inventory``
3. Notify same-process SSE listeners (works even when Redis is down)
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from config.settings import settings
from utils.cache import cache_set, get_redis

logger = logging.getLogger(__name__)

CHANNEL = "shopsphere:inventory"
CACHE_KEY = "inv:variant:{variant_id}"
LOW_STOCK_THRESHOLD = 5

_local_lock = threading.Lock()
_local_queues: List[asyncio.Queue] = []


def build_inventory_event(
    *,
    variant_id: int,
    product_id: int,
    sku: str,
    stock: int,
    product_name: str = "",
    reason: str = "",
    change: int = 0,
) -> Dict[str, Any]:
    return {
        "type": "inventory.update",
        "variant_id": variant_id,
        "product_id": product_id,
        "sku": sku,
        "stock": stock,
        "product_name": product_name,
        "reason": reason,
        "change": change,
        "low_stock": stock < LOW_STOCK_THRESHOLD,
        "out_of_stock": stock <= 0,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def publish_inventory_update(
    *,
    variant_id: int,
    product_id: int,
    sku: str,
    stock: int,
    product_name: str = "",
    reason: str = "",
    change: int = 0,
) -> Dict[str, Any]:
    """Publish a stock change to Redis + local SSE subscribers. Never raises."""
    event = build_inventory_event(
        variant_id=variant_id,
        product_id=product_id,
        sku=sku,
        stock=stock,
        product_name=product_name,
        reason=reason,
        change=change,
    )

    # Local SSE bus first (sync, never touches the network)
    _fanout_local(event)

    def _redis_side_effects() -> None:
        try:
            cache_set(
                CACHE_KEY.format(variant_id=variant_id),
                event,
                ttl=settings.cache_ttl_seconds,
            )
        except Exception:
            logger.debug("inventory cache_set failed", exc_info=True)
        client = get_redis()
        if not client:
            return
        try:
            client.publish(CHANNEL, json.dumps(event, default=str))
        except Exception:
            logger.debug("inventory redis publish failed", exc_info=True)

    # Never block request/test threads on Redis / Celery
    threading.Thread(target=_redis_side_effects, daemon=True).start()

    if stock < LOW_STOCK_THRESHOLD:
        _maybe_notify_low_stock(event)

    return event


def _fanout_local(event: Dict[str, Any]) -> None:
    with _local_lock:
        queues = list(_local_queues)
    for queue in queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
        except Exception:
            logger.debug("local inventory fanout failed", exc_info=True)


def _maybe_notify_low_stock(event: Dict[str, Any]) -> None:
    """Fire-and-forget low-stock alert — never block the request path."""

    def _run() -> None:
        try:
            from app.workers.tasks import notify_low_stock

            notify_low_stock.delay(
                event.get("product_name") or event["sku"],
                event["sku"],
                int(event["stock"]),
                int(event["variant_id"]),
            )
        except Exception:
            # Celery/Redis may be unavailable in tests / local SQLite runs
            logger.debug("low-stock celery notify skipped", exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


def register_local_subscriber() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    with _local_lock:
        _local_queues.append(queue)
    return queue


def unregister_local_subscriber(queue: asyncio.Queue) -> None:
    with _local_lock:
        if queue in _local_queues:
            _local_queues.remove(queue)


def _event_matches(
    event: Dict[str, Any],
    *,
    variant_ids: Optional[Set[int]],
    product_ids: Optional[Set[int]],
) -> bool:
    if not variant_ids and not product_ids:
        return True
    if variant_ids and int(event.get("variant_id", -1)) in variant_ids:
        return True
    if product_ids and int(event.get("product_id", -1)) in product_ids:
        return True
    return False


async def inventory_event_stream(
    *,
    variant_ids: Optional[Set[int]] = None,
    product_ids: Optional[Set[int]] = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for matching inventory updates."""
    local_q = register_local_subscriber()
    pubsub = None
    client = get_redis()
    if client:
        try:
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(CHANNEL)
        except Exception:
            logger.warning("inventory SSE could not subscribe to Redis; using local bus only")
            pubsub = None

    try:
        yield f"event: ready\ndata: {json.dumps({'ok': True})}\n\n"
        while True:
            sent = False

            # Drain local queue first (same-process updates)
            while True:
                try:
                    event = local_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if _event_matches(event, variant_ids=variant_ids, product_ids=product_ids):
                    yield f"event: inventory\ndata: {json.dumps(event)}\n\n"
                    sent = True

            if pubsub is not None:
                try:
                    message = await asyncio.to_thread(
                        pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    message = None
                    await asyncio.sleep(1.0)
                if message and message.get("type") == "message":
                    try:
                        event = json.loads(message["data"])
                    except (TypeError, json.JSONDecodeError):
                        event = None
                    if event and _event_matches(
                        event, variant_ids=variant_ids, product_ids=product_ids
                    ):
                        yield f"event: inventory\ndata: {json.dumps(event)}\n\n"
                        sent = True
            else:
                await asyncio.sleep(1.0)

            if not sent:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        unregister_local_subscriber(local_q)
        if pubsub is not None:
            try:
                pubsub.unsubscribe(CHANNEL)
                pubsub.close()
            except Exception:
                pass
