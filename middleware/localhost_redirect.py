"""Optional localhost → 127.0.0.1 redirect for HTML navigations only.

IMPORTANT: Never redirect ``/static/*`` (or other assets). Browsers treat
``localhost`` and ``127.0.0.1`` as different origins, so a cross-origin
redirect on stylesheets/scripts causes CSS/JS to be ignored — the page
renders as unstyled “mess”.
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

        path = request.url.path or "/"
        # Assets and APIs must stay same-origin as the page that requested them
        if (
            path.startswith("/static/")
            or path.startswith("/uploads/")
            or path.startswith("/api/")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi")
            or path == "/health"
            or path == "/favicon.ico"
        ):
            return await call_next(request)

        accept = (request.headers.get("accept") or "").lower()
        # Only redirect top-level HTML navigations
        if "text/html" not in accept and "*/*" not in accept:
            return await call_next(request)

        port = request.url.port
        netloc = f"127.0.0.1:{port}" if port else "127.0.0.1"
        target = request.url.replace(netloc=netloc)
        return RedirectResponse(url=str(target), status_code=302)
