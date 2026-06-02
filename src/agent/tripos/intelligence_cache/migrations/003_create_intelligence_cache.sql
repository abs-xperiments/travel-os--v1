-- Migration 003: cache for retrieved trip enrichment (stays + restaurants + weather).
--
-- Forward-only. Keyed by destination id; stores one TripEnrichment as jsonb so a destination's
-- stays/restaurants/weather are fetched once and reused until stale.

CREATE TABLE IF NOT EXISTS tripos_intelligence_cache (
    key        text PRIMARY KEY,                    -- e.g. "munnar"
    data       jsonb NOT NULL,                       -- a serialized TripEnrichment
    fetched_at timestamptz NOT NULL DEFAULT now()
);
