-- Migration 002: cache for retrieved destination knowledge.
--
-- Forward-only (see agent.services.db.apply_migrations). When we retrieve a destination from
-- the web (because it isn't in the curated catalog), we store the resulting Destination here
-- so future trips to the same place are instant and free until the data goes stale.

CREATE TABLE IF NOT EXISTS tripos_destination_cache (
    id         text PRIMARY KEY,                    -- slug, e.g. "pondicherry"
    name       text NOT NULL,
    knowledge  jsonb NOT NULL,                       -- a serialized Destination (with attractions)
    fetched_at timestamptz NOT NULL DEFAULT now()    -- for freshness / TTL
);
