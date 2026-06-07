-- Email authentication removed (user decision 2026-06-08): Google is the only sign-in
-- method. These tables held only ephemeral secrets (hashed codes/tokens, rate counters) —
-- nothing of value is lost. Forward-only cleanup so the schema matches the code's story.

DROP TABLE IF EXISTS tripos_login_codes;
DROP TABLE IF EXISTS tripos_login_tokens;
DROP TABLE IF EXISTS tripos_email_sends;
