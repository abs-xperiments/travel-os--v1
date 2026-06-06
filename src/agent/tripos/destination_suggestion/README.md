# destination_suggestion

**What it does, in one line:** answers *"where should I go?"* with 3–5 real, constraint-fitting
destination ideas — before any trip planning happens.

## Why it exists

Not every traveler knows their destination. "Where should I go for 5 days in December with
₹40,000?" is a *discovery* question, not a planning one — the traveler shouldn't be
interrogated about pace and interests before getting ideas. This module turns their
constraints (days, month, budget, interests, region) into ranked suggestions, each with a
why, the season fit, a rough per-person cost, and one honest tradeoff.

## How it works, step by step

1. The planner agent's `suggest_destinations` tool calls `suggest(...)` here.
2. `suggest` asks the registry for the `destination_suggestion` provider — today that's
   `WebDestinationSuggester` (`providers/destination_suggestions.py`).
3. The provider checks `intelligence_cache` under a constraint-keyed row
   (`suggest:{region}:{days}:{month}:{budget}:{interests}:v1`) — a repeat ask is ~free.
4. On a miss it runs ONE `research()` web call + one structured extraction
   (`DestinationIdeas`), then caches the result.
5. The tool ranks the ideas **best budget fit first** (reusing the same
   `budget_compatibility` logic circuits use — affordability never outranked by fame) and
   returns a recommended pick + alternatives.

Best-effort throughout: any failure returns `[]` and the agent says so honestly — it never
invents destinations.

## How to debug it

- No suggestions coming back? Check `logs/agent.log` for "destination suggestion failed".
- Stale answers after a prompt change? The cache key ends in `:v1` — bump it when the
  payload shape changes (same convention as the enrichment cache's `:v2`).
- Inspect cached rows: `SELECT key, fetched_at FROM tripos_intelligence_cache WHERE key LIKE 'suggest:%'`.
