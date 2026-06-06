-- Every trip belongs to exactly one user. NULL = legacy pre-accounts trips, which are
-- claimed (once) by the first user ever created — see accounts.find_or_create_user.
-- Requires 001 (tripos_trips) and 004 (tripos_users): lifespan applies trip_store's
-- migrations before accounts', and 004 sorts before 005 within this directory.

ALTER TABLE tripos_trips
    ADD COLUMN IF NOT EXISTS user_id text REFERENCES tripos_users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS tripos_trips_user_updated_idx
    ON tripos_trips (user_id, updated_at DESC);
