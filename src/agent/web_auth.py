"""Auth routes — passwordless sign-in (magic link now, Google when configured).

Mounted by tripos_web. The flow in one breath: /login offers Google + email; the email
path mints a single-use token and mails a link; the link's GET shows a confirm page
(mail scanners prefetch GETs — they must never spend the token); the confirm POST
consumes it atomically, finds-or-creates the ONE account for that email, and mints a
session. New email users get asked their name once (/welcome). Logout is a POST.

Design notes that matter (docs/failure_modes.md "Accounts"):
- responses to /auth/email are identical for new/existing/rate-limited addresses;
- no ?next= redirect parameter exists, anywhere;
- the trip cookie is cleared on login so a shared device never carries another
  user's current-trip into a fresh session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from agent.config import get_settings
from agent.services import email as email_service
from agent.tripos import accounts

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

router = APIRouter()

SID_COOKIE = "tripos_sid"  # the session token (raw; DB stores only its hash)
TRIP_COOKIE = "tripos_session"  # the current-trip id (set by tripos_web)


def set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        SID_COOKIE,
        raw_token,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        max_age=60 * 60 * 24 * accounts.SESSION_TTL_DAYS,
        path="/",
    )


async def _sign_in(response: Response, user_id: str) -> None:
    """Fresh session + cookie; clears any stale current-trip from this device."""
    raw = await accounts.create_session(user_id)
    set_session_cookie(response, raw)
    response.delete_cookie(TRIP_COOKIE, path="/")


@router.get("/login")
async def login_page(request: Request) -> Response:
    if getattr(request.state, "user", None) is not None:
        return RedirectResponse("/", status_code=303)
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
            "sent": False,
        },
    )


@router.post("/auth/email")
async def auth_email(request: Request, email: Annotated[str, Form()]) -> Response:
    """Send a sign-in link. The response is IDENTICAL whatever happens (no enumeration)."""
    settings = get_settings()
    address = email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    try:
        if "@" in address and await accounts.send_allowed(address, ip):
            raw = await accounts.create_login_token(address)
            link = f"{settings.app_base_url.rstrip('/')}/auth/verify?token={raw}"
            await email_service.send_magic_link(address, link)
    except Exception:
        # Logged for us; the user still sees the generic page (and can retry).
        logger.exception("magic-link send failed for {}", address)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
            "sent": True,
            "sent_to": address,
        },
    )


@router.get("/auth/verify")
async def verify_landing(request: Request, token: str = "") -> Response:
    """The magic link's GET — validates but NEVER consumes (scanner-prefetch-safe)."""
    email_addr = await accounts.peek_login_token(token) if token else None
    return templates.TemplateResponse(
        request,
        "auth_confirm.html",
        {"token": token if email_addr else None, "email": email_addr},
    )


@router.post("/auth/verify")
async def verify_consume(request: Request, token: Annotated[str, Form()]) -> Response:
    """The confirm button — atomically spends the token and signs the user in."""
    email_addr = await accounts.consume_login_token(token)
    if email_addr is None:  # spent or expired — friendly retry page
        return templates.TemplateResponse(
            request, "auth_confirm.html", {"token": None, "email": None}
        )
    user, created = await accounts.find_or_create_user(email_addr, provider="email")
    destination = "/welcome" if created and not user.name else "/"
    response = RedirectResponse(destination, status_code=303)
    await _sign_in(response, user.id)
    return response


@router.get("/welcome")
async def welcome_page(request: Request) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "welcome.html", {"user": user})


@router.post("/welcome")
async def welcome_save(request: Request, name: Annotated[str, Form()]) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    cleaned = " ".join(name.split())[:80]
    if cleaned:
        await accounts.update_profile(user.id, name=cleaned)
    return RedirectResponse("/", status_code=303)


@router.post("/auth/logout")
async def logout(request: Request) -> Response:
    raw = request.cookies.get(SID_COOKIE)
    if raw:
        await accounts.delete_session(raw)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SID_COOKIE, path="/")
    response.delete_cookie(TRIP_COOKIE, path="/")
    return response


@router.get("/profile")
async def profile_page(request: Request) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "profile.html", {"user": user, "saved": False})


@router.post("/profile")
async def profile_save(request: Request, name: Annotated[str, Form()]) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    cleaned = " ".join(name.split())[:80]
    if cleaned and cleaned != user.name:
        await accounts.update_profile(user.id, name=cleaned)
        user = await accounts.get_user(user.id) or user
    return templates.TemplateResponse(request, "profile.html", {"user": user, "saved": True})


@router.post("/auth/logout-everywhere")
async def logout_everywhere(request: Request) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    await accounts.delete_all_sessions(user.id)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SID_COOKIE, path="/")
    response.delete_cookie(TRIP_COOKIE, path="/")
    return response
