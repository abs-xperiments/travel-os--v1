"""accounts — passwordless users, sessions, and single-use sign-in tokens.

The auth model in one paragraph: a user proves control of an inbox (magic link) or a
Google account; we find-or-create ONE user per lowercased email (signup and login are the
same operation — the system decides which happened). A successful auth mints a server-side
session whose raw token lives only in the browser cookie; the database stores sha256
hashes of every secret, so a database read can never be replayed as a credential.

Security decisions baked in (see docs/failure_modes.md "Accounts"):
- Sign-in tokens are SINGLE-USE, consumed by an atomic conditional UPDATE — a double
  click (or a mail scanner racing the human) yields exactly one winner.
- Sessions roll: ~90 days from last activity, with the touch throttled to once a day.
- The FIRST user ever created claims all legacy (pre-accounts) trips, inside the same
  transaction that creates the user — race-free and exactly-once.
- Rate limiting is enforced in the DB (per-email and per-IP hourly caps).

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from agent.services import db

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

LOGIN_CODE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 40
SESSION_TTL_DAYS = 90
SESSION_TOUCH_INTERVAL = "1 day"  # roll the expiry at most this often (write throttling)
MAX_SENDS_PER_EMAIL_PER_HOUR = 5
MAX_SENDS_PER_IP_PER_HOUR = 20


class User(BaseModel):
    """One TripOS account (signup and login both resolve to this, keyed by email)."""

    id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None
    auth_provider: str
    created_at: datetime
    last_login_at: datetime | None = None


def _hash(raw: str) -> str:
    """sha256 hex of a raw secret — the only form we ever store."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def init_db() -> list[str]:
    """Apply the accounts migrations (004 users/sessions/tokens, 005 trips.user_id).

    Call AFTER trip_store.init_db(): 005 alters tripos_trips, which 001 creates.
    """
    return await db.apply_migrations(MIGRATIONS_DIR)


# ------------------------------------------------------------------- users


def _user_from(row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
        auth_provider=row["auth_provider"],
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
    )


async def get_user(user_id: str) -> User | None:
    row = await db.fetchrow("SELECT * FROM tripos_users WHERE id = $1", user_id)
    return _user_from(row) if row else None


async def find_or_create_user(
    email: str,
    provider: str,
    name: str | None = None,
    avatar_url: str | None = None,
) -> tuple[User, bool]:
    """ONE account per email — signup and login are the same call.

    Returns (user, created). On a match, fills in name/avatar only where empty (a Google
    login enriches an email-created account, never overwrites what the user set) and
    stamps last_login_at. On create, the FIRST user ever also claims all legacy
    (user_id IS NULL) trips — done inside this same transaction so it's exactly-once
    even under concurrent first signups.
    """
    email = _normalize_email(email)
    async with db.transaction() as conn:
        row = await conn.fetchrow("SELECT * FROM tripos_users WHERE email = $1", email)
        if row is not None:
            row = await conn.fetchrow(
                "UPDATE tripos_users SET last_login_at = now(), "
                "  name = COALESCE(name, $2), avatar_url = COALESCE(avatar_url, $3) "
                "WHERE email = $1 RETURNING *",
                email,
                name,
                avatar_url,
            )
            assert row is not None
            return _user_from(row), False

        user_id = uuid.uuid4().hex
        row = await conn.fetchrow(
            "INSERT INTO tripos_users (id, email, name, avatar_url, auth_provider, last_login_at)"
            " VALUES ($1, $2, $3, $4, $5, now()) RETURNING *",
            user_id,
            email,
            name,
            avatar_url,
            provider,
        )
        assert row is not None
        # Legacy claim: if this INSERT made the very first account, it inherits every
        # pre-accounts trip. The count check inside the transaction makes this race-safe:
        # concurrent first signups serialize on the unique email/PK, and only the one
        # that observes count==1 claims.
        total = await conn.fetchval("SELECT count(*) FROM tripos_users")
        if total == 1:
            await conn.execute(
                "UPDATE tripos_trips SET user_id = $1 WHERE user_id IS NULL", user_id
            )
        return _user_from(row), True


async def update_profile(
    user_id: str, name: str | None = None, avatar_url: str | None = None
) -> None:
    """Update the editable profile fields (only the ones provided)."""
    if name is not None:
        await db.execute("UPDATE tripos_users SET name = $2 WHERE id = $1", user_id, name)
    if avatar_url is not None:
        await db.execute(
            "UPDATE tripos_users SET avatar_url = $2 WHERE id = $1", user_id, avatar_url
        )


# ----------------------------------------------------------------- sessions


async def create_session(user_id: str) -> str:
    """Mint a fresh session; returns the RAW token (cookie value). DB stores the hash."""
    raw = secrets.token_urlsafe(32)
    await db.execute(
        "INSERT INTO tripos_sessions (token_hash, user_id, expires_at) "
        f"VALUES ($1, $2, now() + interval '{SESSION_TTL_DAYS} days')",
        _hash(raw),
        user_id,
    )
    return raw


async def resolve_session(raw_token: str) -> User | None:
    """The user for a session cookie, or None. Rolls the expiry (throttled to daily)."""
    token_hash = _hash(raw_token)
    row = await db.fetchrow(
        "SELECT u.* FROM tripos_sessions s JOIN tripos_users u ON u.id = s.user_id "
        "WHERE s.token_hash = $1 AND s.expires_at > now()",
        token_hash,
    )
    if row is None:
        return None
    # Rolling expiry without a write per request: touch at most once per interval.
    await db.execute(
        "UPDATE tripos_sessions SET last_seen_at = now(), "
        f"  expires_at = now() + interval '{SESSION_TTL_DAYS} days' "
        f"WHERE token_hash = $1 AND last_seen_at < now() - interval '{SESSION_TOUCH_INTERVAL}'",
        token_hash,
    )
    return _user_from(row)


async def delete_session(raw_token: str) -> None:
    """Log out this device."""
    await db.execute("DELETE FROM tripos_sessions WHERE token_hash = $1", _hash(raw_token))


async def delete_all_sessions(user_id: str) -> None:
    """Log out everywhere."""
    await db.execute("DELETE FROM tripos_sessions WHERE user_id = $1", user_id)


# ----------------------------------------------------------- verification codes


def _code_hash(email: str, code: str) -> str:
    """Codes are bound to the address they were sent to — a code for one inbox can never
    verify another."""
    return _hash(f"{_normalize_email(email)}:{code}")


async def create_login_code(email: str) -> str:
    """Mint a fresh 6-digit code for this email; returns the RAW code (for the email body).

    Requesting a new code INVALIDATES every previous unused code for the address — only
    the latest email is ever valid (the spec's resend behavior).
    """
    email = _normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.execute(
        "UPDATE tripos_login_codes SET used_at = now() WHERE email = $1 AND used_at IS NULL",
        email,
    )
    await db.execute(
        "INSERT INTO tripos_login_codes (email, code_hash, expires_at) "
        f"VALUES ($1, $2, now() + interval '{LOGIN_CODE_TTL_MINUTES} minutes')",
        email,
        _code_hash(email, code),
    )
    return code


async def seconds_until_resend(email: str) -> int:
    """How long before this address may request another code (0 = now). Server-side
    enforcement of the resend cooldown — the UI countdown alone is just decoration."""
    created = await db.fetchval(
        "SELECT created_at FROM tripos_login_codes "
        "WHERE email = $1 ORDER BY created_at DESC LIMIT 1",
        _normalize_email(email),
    )
    if created is None:
        return 0
    remaining = await db.fetchval(
        f"SELECT GREATEST(0, CEIL(EXTRACT(EPOCH FROM "
        f"($1::timestamptz + interval '{RESEND_COOLDOWN_SECONDS} seconds') - now())))::int",
        created,
    )
    return int(remaining or 0)


async def verify_login_code(email: str, code: str) -> str:
    """Check a code against the LATEST one sent to this address.

    Returns one of: "ok" (consumed — race-safe, exactly one winner), "invalid" (wrong
    code; counts an attempt), "expired", "too_many" (attempt cap hit), "none" (no code
    outstanding). Every state maps to a specific, honest message in the UI.
    """
    email = _normalize_email(email)
    row = await db.fetchrow(
        "SELECT id, code_hash, expires_at < now() AS expired, attempts "
        "FROM tripos_login_codes WHERE email = $1 AND used_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        email,
    )
    if row is None:
        return "none"
    if row["expired"]:
        return "expired"
    if row["attempts"] >= MAX_CODE_ATTEMPTS:
        return "too_many"
    if _code_hash(email, code.strip()) != row["code_hash"]:
        attempts = await db.fetchval(
            "UPDATE tripos_login_codes SET attempts = attempts + 1 "
            "WHERE id = $1 RETURNING attempts",
            row["id"],
        )
        return "too_many" if attempts is not None and attempts >= MAX_CODE_ATTEMPTS else "invalid"
    consumed = await db.fetchrow(
        "UPDATE tripos_login_codes SET used_at = now() "
        "WHERE id = $1 AND used_at IS NULL RETURNING id",
        row["id"],
    )
    return "ok" if consumed is not None else "invalid"  # race: someone else won


# ---------------------------------------------------------------- rate limits


async def send_allowed(email: str, ip: str) -> bool:
    """May we send a sign-in email to this address from this IP right now?

    Caps are enforced quietly — the caller responds identically either way, so the
    endpoint can't be used to probe accounts or the limiter.
    """
    email = _normalize_email(email)
    by_email = await db.fetchval(
        "SELECT count(*) FROM tripos_email_sends "
        "WHERE email = $1 AND created_at > now() - interval '1 hour'",
        email,
    )
    if by_email is not None and by_email >= MAX_SENDS_PER_EMAIL_PER_HOUR:
        return False
    by_ip = await db.fetchval(
        "SELECT count(*) FROM tripos_email_sends "
        "WHERE ip = $1 AND created_at > now() - interval '1 hour'",
        ip,
    )
    if by_ip is not None and by_ip >= MAX_SENDS_PER_IP_PER_HOUR:
        return False
    await db.execute("INSERT INTO tripos_email_sends (email, ip) VALUES ($1, $2)", email, ip)
    return True
