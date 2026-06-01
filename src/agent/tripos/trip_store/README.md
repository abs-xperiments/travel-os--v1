# `trip_store` — the "save & reopen trips" module

## In one sentence
This module saves each conversation (a "trip") to the database so it survives restarts, can
be reopened later from its own link, and shows up in a list of saved trips.

## Why it exists
Until now, conversations lived only in the web server's memory — restart the server and
they're gone. A deployed app restarts regularly, and your vision needs "save my trip, reopen
it later, share it." This module is where a trip becomes durable.

## What a "trip" is
One saved conversation. Its **id** is a long random string that's also used in the URL
(`/trip/<id>`), so the id doubles as an unguessable shareable link. We store two things:
- **transcript** — a simple list of `{role, content}` messages, used to redraw the chat when
  you reopen it (easy to display, no parsing of the AI's internal format).
- **agent_messages** — the AI's own message history, serialized, so when you continue a trip
  the model has the *full* context (including the tool calls it made) and picks up seamlessly.

## What it does (the functions)
- `init_db()` — creates the table on startup (runs the SQL in `migrations/`, once).
- `ensure_trip(id)` — gives you a valid trip id: your existing one, or a brand-new trip.
- `get_trip(id)` — loads a trip and its transcript (or `None`).
- `load_agent_messages(id)` — rebuilds the AI history so the conversation can continue.
- `append_turn(id, you, reply, history)` — saves one back-and-forth and updates the trip.
- `list_recent()` — the saved-trips list for the dashboard (skips empty ones).

## How the data is stored
One table, `tripos_trips`, created by `migrations/001_create_tripos.sql`. **Migrations are
forward-only**: to change the schema, add `002_*.sql` — never edit `001`. The `transcript`
and `agent_messages` columns are `jsonb` (JSON stored in the database).

## How to debug it
- **Trips don't persist / table errors:** the migration didn't run. It runs on web startup;
  check the server logs for "applied migrations". You can also run it by hand:
  `uv run python -c "import asyncio; from agent.tripos import trip_store; asyncio.run(trip_store.init_db())"`.
- **Reopened chat is empty:** check the trip id in the URL matches a row, and that
  `append_turn` ran (it only runs after a successful AI reply).
- **"DATABASE_URL is not set":** add your Neon connection string to `.env` (see the db service).
- **Run the live test:** `uv run pytest -m integration scripts/tests/test_trip_store.py`
  (needs `DATABASE_URL`; it uses throwaway rows and cleans up).

## What it deliberately does NOT do
It doesn't talk to the AI or render anything — it only reads and writes trips. The web layer
(`tripos_web.py`) calls it; the agent (`agents/tripos_planner.py`) does the thinking.
