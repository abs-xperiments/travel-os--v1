-- 6-digit email verification codes (replaces magic links, 2026-06-08).
-- Codes are stored as sha256(email + ':' + code) — bound to the address they were sent
-- to, never reusable across addresses, and unreadable from a DB leak. attempts counts
-- wrong guesses; at the cap the code is dead regardless of expiry. The old
-- tripos_login_tokens table is left in place but unused (cleanup later).

CREATE TABLE IF NOT EXISTS tripos_login_codes (
    id         bigserial PRIMARY KEY,
    email      text NOT NULL,                       -- lowercased
    code_hash  text NOT NULL,                       -- sha256(email:code), hex
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,                -- created_at + 10 min
    used_at    timestamptz,                         -- NULL until consumed or invalidated
    attempts   int NOT NULL DEFAULT 0               -- wrong guesses against THIS code
);
CREATE INDEX IF NOT EXISTS tripos_login_codes_email_idx
    ON tripos_login_codes (email, created_at DESC);
