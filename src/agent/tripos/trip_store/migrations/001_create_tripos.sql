-- Migration 001: the table behind TripOS persistence.
--
-- Forward-only, runs once in filename order (see agent.services.db.apply_migrations).
-- A "trip" is a saved conversation: its id (a uuid hex) is unguessable and used directly
-- in the URL (/trip/{id}), so it doubles as the shareable link.

CREATE TABLE IF NOT EXISTS tripos_trips (
    id             text PRIMARY KEY,                    -- uuid4 hex; also the share URL
    title          text,                                -- derived from the first message
    transcript     jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{role, content}] for display
    agent_messages jsonb,                                -- serialized pydantic-ai history (for continuation)
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

-- Dashboard lists most-recently-updated trips first.
CREATE INDEX IF NOT EXISTS tripos_trips_updated_idx ON tripos_trips (updated_at DESC);
