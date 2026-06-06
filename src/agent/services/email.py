"""Email sending via Resend (https://resend.com) — used for magic-link sign-in.

One tiny capability on purpose: `send_magic_link`. Resend is a plain HTTPS API, so this
rides the existing httpx dependency — no SDK. Configure RESEND_API_KEY and RESEND_FROM
(e.g. 'TripOS <onboarding@resend.dev>' while testing, a real domain later).
"""

from __future__ import annotations

import httpx
from loguru import logger

from agent.config import get_settings

_API_URL = "https://api.resend.com/emails"


class EmailNotConfigured(RuntimeError):
    """Raised when RESEND_API_KEY / RESEND_FROM are missing."""


def _require_config() -> tuple[str, str]:
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_from:
        raise EmailNotConfigured(
            "Email sign-in needs RESEND_API_KEY and RESEND_FROM in the environment. "
            "Create a free key at https://resend.com."
        )
    return settings.resend_api_key, settings.resend_from


async def send_magic_link(to: str, link: str) -> None:
    """Send the sign-in email. Raises on failure — the caller decides what the user sees."""
    api_key, sender = _require_config()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": sender,
                "to": [to],
                "subject": "Your TripOS sign-in link",
                "html": (
                    "<p>Tap the button below to sign in to <strong>TripOS</strong> — "
                    "your AI travel partner.</p>"
                    f'<p><a href="{link}" style="display:inline-block;padding:12px 20px;'
                    "background:#0284c7;color:#fff;border-radius:10px;text-decoration:none;"
                    'font-weight:600">Sign in to TripOS</a></p>'
                    f'<p>Or open this link: <a href="{link}">{link}</a></p>'
                    "<p>This link works once and expires in 15 minutes. "
                    "If you didn't request it, you can safely ignore this email.</p>"
                ),
            },
        )
    if response.status_code >= 400:
        logger.error("Resend send failed ({}): {}", response.status_code, response.text[:300])
        response.raise_for_status()
