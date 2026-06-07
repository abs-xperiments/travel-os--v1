"""Tests for the accounts module — passwordless users, sessions, sign-in tokens.

Offline tests cover the pure crypto/normalization helpers. The DB flows are integration
tests (real Neon, throwaway rows, cleaned up in finally).

⚠️ CLEANUP RULE FOR THESE TESTS: tripos_trips.user_id has ON DELETE CASCADE, and the
first-user legacy claim grabs every NULL-user trip. A test user who claimed legacy trips
must be UN-CLAIMED (user_id back to NULL) BEFORE being deleted — otherwise deleting the
test user would cascade-delete real production trips. The helpers below enforce this.

    uv run pytest scripts/tests/test_accounts.py                 # offline only
    uv run pytest scripts/tests/test_accounts.py -m integration  # live DB flows
"""

from __future__ import annotations

import asyncio

import pytest

from agent.tripos import accounts

# ----------------------------------------------------------------- offline


def test_hash_is_sha256_hex_and_deterministic():
    h1 = accounts._hash("token-a")
    h2 = accounts._hash("token-a")
    h3 = accounts._hash("token-b")
    assert h1 == h2 and h1 != h3
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)


def test_email_normalization_lowercases_and_trims():
    assert accounts._normalize_email("  Abirami.MOA@Gmail.COM ") == "abirami.moa@gmail.com"


# -------------------------------------------------------------- integration

pytestmark_integration = pytest.mark.integration


async def _safe_delete_user(user_id: str) -> None:
    """Un-claim any trips first (NULL them back), THEN delete — never cascade prod trips."""
    from agent.services import db

    await db.execute("UPDATE tripos_trips SET user_id = NULL WHERE user_id = $1", user_id)
    await db.execute("DELETE FROM tripos_users WHERE id = $1", user_id)


@pytest.mark.integration
async def test_find_or_create_is_one_account_per_email():
    await accounts.init_db()
    created_ids: list[str] = []
    try:
        u1, created1 = await accounts.find_or_create_user("Test.Accounts@Example.com", "email")
        created_ids.append(u1.id)
        assert created1 is True
        assert u1.email == "test.accounts@example.com"  # lowercased

        # Same inbox, different casing, different provider -> SAME account, enriched not duped.
        u2, created2 = await accounts.find_or_create_user(
            "test.accounts@example.COM", "google", name="Abi", avatar_url="http://x/y.png"
        )
        assert created2 is False
        assert u2.id == u1.id
        assert u2.name == "Abi"  # filled where empty
        assert u2.auth_provider == "email"  # first provider is kept, not overwritten
    finally:
        for uid in created_ids:
            await _safe_delete_user(uid)


@pytest.mark.integration
async def test_verification_code_full_matrix():
    """6 digits, one-time, email-bound, attempt-capped, resend-invalidates — the whole spec."""
    from agent.services import db

    await accounts.init_db()
    email = "test.codes@example.com"
    try:
        code = await accounts.create_login_code(email)
        assert len(code) == 6 and code.isdigit()

        # Email binding: the right code against a DIFFERENT address never verifies.
        assert await accounts.verify_login_code("other@example.com", code) == "none"

        # Wrong guesses count attempts; the cap kills the code (4 invalid, 5th -> too_many).
        for _ in range(accounts.MAX_CODE_ATTEMPTS - 1):
            assert await accounts.verify_login_code(email, "000000") == "invalid"
        assert await accounts.verify_login_code(email, "000000") == "too_many"
        # Even the CORRECT code is dead after the cap.
        assert await accounts.verify_login_code(email, code) == "too_many"

        # Resend mints a new code and invalidates everything before it: the OLD code is
        # now just a wrong guess against the new one (costs an attempt, never verifies).
        code2 = await accounts.create_login_code(email)
        assert await accounts.verify_login_code(email, code) == "invalid"
        # Concurrent double-submit of the right code: exactly ONE winner.
        a, b = await asyncio.gather(
            accounts.verify_login_code(email, code2),
            accounts.verify_login_code(email, code2),
        )
        assert sorted([a, b]) == ["invalid", "ok"]
        # Spent code can't be used again.
        assert await accounts.verify_login_code(email, code2) == "none"

        # Server-side resend cooldown is live right after a send.
        await accounts.create_login_code(email)
        assert 0 < await accounts.seconds_until_resend(email) <= accounts.RESEND_COOLDOWN_SECONDS
    finally:
        await db.execute("DELETE FROM tripos_login_codes WHERE email = ANY($1)", [email])
        await db.execute("DELETE FROM tripos_email_sends WHERE email = $1", email)


@pytest.mark.integration
async def test_sessions_roll_resolve_and_logout_everywhere():
    await accounts.init_db()
    user, _ = await accounts.find_or_create_user("test.sessions@example.com", "email")
    try:
        raw1 = await accounts.create_session(user.id)
        raw2 = await accounts.create_session(user.id)
        assert raw1 != raw2  # fresh token per login

        resolved = await accounts.resolve_session(raw1)
        assert resolved is not None and resolved.id == user.id
        assert await accounts.resolve_session("not-a-real-token") is None

        await accounts.delete_session(raw1)
        assert await accounts.resolve_session(raw1) is None  # this device logged out
        assert await accounts.resolve_session(raw2) is not None  # others intact

        await accounts.delete_all_sessions(user.id)
        assert await accounts.resolve_session(raw2) is None  # signed out everywhere
    finally:
        await _safe_delete_user(user.id)


@pytest.mark.integration
async def test_first_user_claims_legacy_trips_second_does_not():
    """Run ONLY when no real users exist yet (pre-cutover) — guarded below."""
    from agent.services import db

    await accounts.init_db()
    existing = await db.fetchval("SELECT count(*) FROM tripos_users")
    if existing and existing > 0:
        pytest.skip("real users exist — the one-time legacy claim has already happened")

    legacy_id = "test-legacy-trip-claim"
    await db.execute("INSERT INTO tripos_trips (id) VALUES ($1) ON CONFLICT DO NOTHING", legacy_id)
    first = second = None
    try:
        first, _ = await accounts.find_or_create_user("test.claim.first@example.com", "email")
        owner = await db.fetchval("SELECT user_id FROM tripos_trips WHERE id = $1", legacy_id)
        assert owner == first.id  # the first account ever claims legacy trips

        second, _ = await accounts.find_or_create_user("test.claim.second@example.com", "email")
        owner = await db.fetchval("SELECT user_id FROM tripos_trips WHERE id = $1", legacy_id)
        assert owner == first.id  # the second account claims NOTHING
    finally:
        await db.execute("DELETE FROM tripos_trips WHERE id = $1", legacy_id)
        for u in (second, first):  # un-claim + delete (never cascade real trips)
            if u is not None:
                await _safe_delete_user(u.id)


@pytest.mark.integration
async def test_send_rate_limit_caps_per_email():
    from agent.services import db

    await accounts.init_db()
    email = "test.ratelimit@example.com"
    try:
        allowed = [await accounts.send_allowed(email, "203.0.113.7") for _ in range(6)]
        assert allowed[: accounts.MAX_SENDS_PER_EMAIL_PER_HOUR] == [True] * 5
        assert allowed[accounts.MAX_SENDS_PER_EMAIL_PER_HOUR] is False  # the 6th is refused
    finally:
        await db.execute("DELETE FROM tripos_email_sends WHERE email = $1", email)
        await db.execute("DELETE FROM tripos_login_tokens WHERE email = $1", email)
