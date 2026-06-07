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

import secrets
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, File, Form, Request, Response, UploadFile
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


def _login_ctx(request: Request, **extra: object) -> dict:
    settings = get_settings()
    return {
        "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
        "stage": "email",
        "error": None,
        **extra,
    }


@router.get("/login")
async def login_page(request: Request) -> Response:
    if getattr(request.state, "user", None) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", _login_ctx(request))


@router.post("/auth/email")
async def auth_email(request: Request, email: Annotated[str, Form()]) -> Response:
    """Send (or resend) a 6-digit verification code.

    Two failure classes, two behaviors (the lesson of the silent-outage bug): anything
    ADDRESS-related stays generic — the code page renders the same whether the account
    exists or the rate cap was hit (no enumeration, no limiter oracle). But a SYSTEM
    failure (provider down, sender misconfigured) is surfaced honestly — pretending we
    sent an email we know we didn't is a lie, not security.
    """
    address = email.strip().lower()
    if "@" not in address:
        return templates.TemplateResponse(
            request, "login.html", _login_ctx(request, error="That doesn't look like an email.")
        )
    ip = request.client.host if request.client else "unknown"

    cooldown = await accounts.seconds_until_resend(address)
    if cooldown > 0:  # server-enforced resend cooldown — the UI timer is just decoration
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_ctx(request, stage="code", email=address, cooldown=cooldown),
        )

    if await accounts.send_allowed(address, ip):
        code = await accounts.create_login_code(address)
        try:
            await email_service.send_verification_code(address, code)
        except email_service.EmailNotConfigured:
            logger.error("email sign-in attempted but Resend is not configured")
            return templates.TemplateResponse(
                request,
                "login.html",
                _login_ctx(request, error="Email sign-in isn't available right now."),
            )
        except email_service.EmailDeliveryError:
            return templates.TemplateResponse(
                request,
                "login.html",
                _login_ctx(
                    request,
                    error="We couldn't send the email right now — please try again in a minute.",
                ),
            )
    # Rate-capped sends fall through to the same page as successful ones (no oracle).
    return templates.TemplateResponse(
        request,
        "login.html",
        _login_ctx(request, stage="code", email=address, cooldown=accounts.RESEND_COOLDOWN_SECONDS),
    )


_CODE_ERRORS = {
    "invalid": "That code isn't right — check the most recent email.",
    "none": "That code isn't right — check the most recent email.",
    "expired": "That code has expired — send yourself a new one.",
    "too_many": "Too many attempts — request a new code to continue.",
}


@router.post("/auth/code")
async def auth_code(
    request: Request, email: Annotated[str, Form()], code: Annotated[str, Form()]
) -> Response:
    """Verify the 6-digit code and sign the user in (find-or-create, one account per email)."""
    address = email.strip().lower()
    outcome = await accounts.verify_login_code(address, code)
    if outcome != "ok":
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_ctx(
                request,
                stage="code",
                email=address,
                cooldown=await accounts.seconds_until_resend(address),
                error=_CODE_ERRORS.get(outcome, _CODE_ERRORS["invalid"]),
                code_dead=outcome in ("expired", "too_many"),
            ),
        )
    user, created = await accounts.find_or_create_user(address, provider="email")
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


# --------------------------------------------------------------- Google OAuth
# Manual flow over httpx (no new dependencies). Profile comes from Google's userinfo
# endpoint — a server-to-server TLS call — so we never decode an id_token without
# signature verification. The button only renders when both credentials are configured.

_STATE_COOKIE = "tripos_oauth_state"
_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def _google_redirect_uri() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/auth/google/callback"


@router.get("/auth/google")
async def google_start(request: Request) -> Response:
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret):
        return RedirectResponse("/login", status_code=303)
    state = secrets.token_urlsafe(32)  # CSRF guard for the round-trip
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": _google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
    )
    response = RedirectResponse(f"{_GOOGLE_AUTH}?{params}", status_code=303)
    response.set_cookie(
        _STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=600,
        path="/",
    )
    return response


@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "") -> Response:
    settings = get_settings()
    expected = request.cookies.get(_STATE_COOKIE, "")
    if not code or not state or not secrets.compare_digest(state, expected):
        logger.warning("google oauth: state mismatch or missing code")
        return RedirectResponse("/login", status_code=303)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_res = await client.post(
                _GOOGLE_TOKEN,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": _google_redirect_uri(),  # must match the start byte-for-byte
                    "grant_type": "authorization_code",
                },
            )
            token_res.raise_for_status()
            access_token = token_res.json().get("access_token", "")
            info_res = await client.get(
                _GOOGLE_USERINFO, headers={"Authorization": f"Bearer {access_token}"}
            )
            info_res.raise_for_status()
            info = info_res.json()
    except Exception:
        logger.exception("google oauth exchange failed")
        return RedirectResponse("/login", status_code=303)

    email_addr = (info.get("email") or "").strip().lower()
    # The merge-safety guard: only a Google-VERIFIED email may find-or-create (merge into)
    # the account for that address — an unverified one could hijack someone's account.
    if not email_addr or info.get("email_verified") is not True:
        logger.warning("google oauth: refused unverified email")
        return RedirectResponse("/login", status_code=303)

    user, created = await accounts.find_or_create_user(
        email_addr,
        provider="google",
        name=info.get("name"),
        avatar_url=info.get("picture"),
    )
    destination = "/welcome" if created and not user.name else "/"
    response = RedirectResponse(destination, status_code=303)
    response.delete_cookie(_STATE_COOKIE, path="/")
    await _sign_in(response, user.id)
    return response


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


# Avatar upload: strict allow-list, hard size cap, suffix derived from the VALIDATED
# content-type (never the client's filename), random UUID key in R2 under avatars/.
_AVATAR_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_AVATAR_MAX_BYTES = 2 * 1024 * 1024


@router.post("/profile/avatar")
async def profile_avatar(request: Request, photo: Annotated[UploadFile, File()]) -> Response:
    user = getattr(request.state, "user", None)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    suffix = _AVATAR_TYPES.get(photo.content_type or "")
    error = None
    if suffix is None:
        error = "Please choose a PNG, JPEG, or WebP image."
    else:
        data = await photo.read()
        if len(data) > _AVATAR_MAX_BYTES:
            error = "That image is over 2 MB — please pick a smaller one."
        else:
            try:
                from agent.services import storage

                key = await storage.store_bytes(
                    data, suffix=suffix, prefix="avatars", content_type=photo.content_type
                )
                await accounts.update_profile(user.id, avatar_url=storage.public_url(key))
                user = await accounts.get_user(user.id) or user
            except Exception:
                logger.exception("avatar upload failed")
                error = "Couldn't save that photo right now — try again in a moment."
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": user, "saved": error is None, "error": error},
    )


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
