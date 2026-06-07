"""Email sending via Resend (https://resend.com) — the sign-in verification codes.

One capability on purpose: `send_verification_code`. Resend is a plain HTTPS API, so this
rides the existing httpx dependency. Configure RESEND_API_KEY and RESEND_FROM — and note
that until a custom domain is verified in Resend, the onboarding sender can ONLY deliver
to the Resend account owner's address (this exact restriction once shipped as a silent
outage — see journal 2026-06-08). Delivery failures raise EmailDeliveryError so the web
layer can be HONEST about a system failure instead of hiding it behind the generic
no-enumeration response.
"""

from __future__ import annotations

import httpx
from loguru import logger

from agent.config import get_settings

_API_URL = "https://api.resend.com/emails"


class EmailNotConfigured(RuntimeError):
    """RESEND_API_KEY / RESEND_FROM are missing."""


class EmailDeliveryError(RuntimeError):
    """Resend refused or failed the send — a SYSTEM failure the user should hear about."""


def _require_config() -> tuple[str, str]:
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_from:
        raise EmailNotConfigured(
            "Email sign-in needs RESEND_API_KEY and RESEND_FROM in the environment. "
            "Create a free key at https://resend.com."
        )
    return settings.resend_api_key, settings.resend_from


async def send_verification_code(to: str, code: str) -> None:
    """Send the 6-digit sign-in code. Raises EmailDeliveryError on any send failure."""
    api_key, sender = _require_config()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": sender,
                    "to": [to],
                    "subject": f"{code} is your TripOS verification code",
                    "html": (
                        "<p>Enter this code to sign in to <strong>TripOS</strong> — "
                        "your AI travel partner:</p>"
                        f'<p style="font-size:34px;font-weight:700;letter-spacing:8px;'
                        f'font-family:monospace">{code}</p>'
                        "<p>The code expires in 10 minutes and works once. "
                        "If you didn't request it, you can safely ignore this email.</p>"
                    ),
                },
            )
    except httpx.HTTPError as exc:  # network/timeout — still a system failure
        logger.error("Resend request failed: {}", exc)
        raise EmailDeliveryError("could not reach the email service") from exc
    if response.status_code >= 400:
        logger.error("Resend send failed ({}): {}", response.status_code, response.text[:300])
        raise EmailDeliveryError(f"email service returned {response.status_code}")
