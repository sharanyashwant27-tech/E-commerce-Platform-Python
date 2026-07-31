"""Redirect browser requests from localhost → 127.0.0.1 on Windows/Docker.

Windows resolves ``localhost`` to ``::1`` first. Docker Desktop often has no
working IPv6 publish on that address, so each asset request waits ~2s before
falling back to IPv4. That makes images look broken and the tab appear stuck.

Forcing the canonical host to 127.0.0.1 makes HTML + CSS + images use IPv4.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class LocalhostRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        host = (request.headers.get("host") or "").split(":")[0].lower()
        if host != "localhost":
            return await call_next(request)

        port = request.url.port
        netloc = f"127.0.0.1:{port}" if port else "127.0.0.1"
        target = request.url.replace(netloc=netloc)
        return RedirectResponse(url=str(target), status_code=307)
