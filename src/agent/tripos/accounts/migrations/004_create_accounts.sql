-- Passwordless accounts: users, server-side sessions, single-use sign-in tokens,
-- and a small send-log for rate limiting. Tokens and session ids are stored as
-- sha256 hashes — the raw secrets live only in the user's email / cookie.

CREATE TABLE IF NOT EXISTS tripos_users (
    id            text PRIMARY KEY,                 -- uuid4 hex
    email         text NOT NULL UNIQUE,             -- stored lowercased; the merge key
    name          text,
    avatar_url    text,
    auth_provider text NOT NULL,                    -- 'email' | 'google' (first provider used)
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE TABLE IF NOT EXISTS tripos_sessions (
    token_hash   text PRIMARY KEY,                  -- sha256(raw cookie token), hex
    user_id      text NOT NULL REFERENCES tripos_users(id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS tripos_sessions_user_idx ON tripos_sessions (user_id);

CREATE TABLE IF NOT EXISTS tripos_login_tokens (
    token_hash text PRIMARY KEY,                    -- sha256(raw link token), hex
    email      text NOT NULL,                       -- lowercased
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    used_at    timestamptz                          -- NULL until consumed (single-use)
);
CREATE INDEX IF NOT EXISTS tripos_login_tokens_email_idx
    ON tripos_login_tokens (email, created_at DESC);

CREATE TABLE IF NOT EXISTS tripos_email_sends (
    id         bigserial PRIMARY KEY,
    email      text NOT NULL,
    ip         text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tripos_email_sends_recent_idx ON tripos_email_sends (created_at DESC);
