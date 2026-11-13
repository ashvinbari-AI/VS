"""
Access-token gate for public deployments.

Enabled only when ACCESS_TOKEN is set (env / .env). Local dev without it is
unchanged. When enabled, every request needs a valid `vs_access` cookie,
except the login page itself and /api/health (used by the docker
healthcheck). Ways in:
  * the /login form (sets the cookie),
  * any URL with ?token=<ACCESS_TOKEN> (sets the cookie, strips the param),
  * an `X-Access-Token: <ACCESS_TOKEN>` header (scripts / curl).
Unauthenticated /api/* calls get a JSON 401; page loads redirect to /login.
"""

from __future__ import annotations

import hashlib
import hmac
from html import escape
from urllib.parse import parse_qs, urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

COOKIE_NAME = "vs_access"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_OPEN_PATHS = {"/login", "/logout", "/api/health", "/favicon.ico"}


def _cookie_value(token: str) -> str:
    # Never store the raw token in the browser; store a derived digest.
    return hashlib.sha256(f"vs-access::{token}".encode()).hexdigest()


def _matches(candidate: str | None, expected: str) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, expected)


def _login_page(error: str | None = None, next_url: str = "/") -> HTMLResponse:
    err = f'<p class="err">{escape(error)}</p>' if error else ""
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Competitor Analysis - Access</title>
<style>
 body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
      font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f6fa;color:#1f2937}}
 form{{background:#fff;padding:32px 36px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.08);width:320px}}
 h1{{font-size:18px;margin:0 0 6px}} p.sub{{margin:0 0 20px;color:#6b7280;font-size:13px}}
 input{{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:14px}}
 button{{margin-top:14px;width:100%;padding:10px;border:0;border-radius:8px;background:#2563eb;color:#fff;
        font-size:14px;cursor:pointer}} button:hover{{background:#1d4ed8}}
 .err{{color:#b91c1c;font-size:13px;margin:0 0 12px}}
</style></head><body>
<form method="post" action="/login">
 <h1>Competitor Analysis</h1><p class="sub">Enter the access token to continue.</p>
 {err}
 <input type="password" name="token" placeholder="Access token" autofocus required>
 <input type="hidden" name="next" value="{escape(next_url)}">
 <button type="submit">Continue</button>
</form></body></html>"""
    return HTMLResponse(html, status_code=401 if error else 200)


def _safe_next(next_url: str | None) -> str:
    # Only allow local paths, never an absolute/protocol-relative redirect.
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


def _set_cookie(resp: Response, token: str) -> Response:
    resp.set_cookie(COOKIE_NAME, _cookie_value(token), max_age=COOKIE_MAX_AGE,
                    httponly=True, samesite="lax", path="/")
    return resp


class AccessTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:  # noqa: ANN001
        super().__init__(app)
        self.token = token
        self.cookie = _cookie_value(token)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        path = request.url.path

        if path == "/logout":
            resp = RedirectResponse("/login", status_code=303)
            resp.delete_cookie(COOKIE_NAME, path="/")
            return resp

        if path == "/login":
            if request.method == "POST":
                form = parse_qs((await request.body()).decode("utf-8", "replace"))
                given = (form.get("token") or [""])[0].strip()
                next_url = _safe_next((form.get("next") or ["/"])[0])
                if _matches(given, self.token):
                    return _set_cookie(RedirectResponse(next_url, status_code=303), self.token)
                return _login_page("Invalid access token.", next_url)
            return _login_page(next_url=_safe_next(request.query_params.get("next")))

        if path in _OPEN_PATHS:
            return await call_next(request)

        # ?token=... magic link: set cookie and redirect to the clean URL.
        q_token = request.query_params.get("token")
        if q_token is not None and _matches(q_token, self.token):
            rest = [(k, v) for k, v in request.query_params.multi_items() if k != "token"]
            clean = path + (f"?{urlencode(rest)}" if rest else "")
            return _set_cookie(RedirectResponse(clean, status_code=303), self.token)

        if (_matches(request.cookies.get(COOKIE_NAME), self.cookie)
                or _matches(request.headers.get("x-access-token"), self.token)):
            return await call_next(request)

        if path.startswith("/api/") or path in ("/docs", "/redoc", "/openapi.json"):
            return JSONResponse(status_code=401, content={
                "success": False, "data": None,
                "error": {"code": "UNAUTHORIZED", "message": "Access token required."},
            })
        nxt = path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?{urlencode({'next': nxt})}", status_code=303)
