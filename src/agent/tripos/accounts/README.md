# accounts

**What it does, in one line:** passwordless user accounts — who you are, your session, and
the single-use links that sign you in.

## Why it exists

TripOS saves trips per person. That needs accounts — but accounts must never become the
experience (the chatbot is the product). So: no passwords, ever. You prove you own an inbox
(emailed sign-in link) or a Google account, and TripOS finds-or-creates the ONE account for
that email. "Sign up" and "Log in" are the same operation; the system works out which one
happened.

## How it works, step by step

1. **Sign-in link:** `create_login_token(email)` mints a random token; the email link carries
   the raw token, the database keeps only its sha256. The link's GET page never spends the
   token (mail scanners prefetch links!) — `peek_login_token` just checks it. The confirm
   button's POST calls `consume_login_token`, an atomic single-winner UPDATE.
2. **Find-or-create:** `find_or_create_user(email, provider, …)` — one row per lowercased
   email. Existing user → stamp last_login, fill empty name/avatar. New user → create; and if
   it's the FIRST account ever, claim every legacy (pre-accounts) trip in the same
   transaction.
3. **Session:** `create_session(user_id)` returns a raw token for the cookie; the DB stores
   the hash. `resolve_session` looks it up and quietly extends the 90-day expiry (at most
   once a day, so reads stay cheap). `delete_session` = logout; `delete_all_sessions` =
   sign out everywhere.
4. **Rate limits:** `send_allowed(email, ip)` caps sign-in emails (5/email/hour, 20/IP/hour)
   using plain DB counts — the web layer answers identically either way, so nothing leaks.

## How to debug it

- "My link doesn't work" → check `tripos_login_tokens`: `used_at` set means something
  consumed it (a second click, or a scanner if the GET ever consumes — it must not);
  `expires_at` past means it aged out (15 min).
- "I keep getting logged out" → `tripos_sessions.expires_at`; rolling renewal only writes
  when `last_seen_at` is older than a day.
- "Wrong trips showing" → should be impossible: trips are scoped by `user_id` in SQL.
  Check `tripos_trips.user_id` and the claim (NULL rows belong to nobody).
- Inspect: `SELECT email, created_at, used_at FROM tripos_login_tokens ORDER BY created_at
  DESC LIMIT 10;`
