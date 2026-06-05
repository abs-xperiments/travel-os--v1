# Learnings

**Stage 6 — Test atomic modules in isolation. Iterate. Keep learnings.**

As you build and test each module on its own, write down what you discover: which
prompt phrasing worked, which model/tier was good enough, surprising failures, costs,
quirks of a service. This saves you (and Claude) from re-learning the same things.

`journal.md` is the *chronological* trace; this file is the *distilled* "here's what we
know now" — keep it tidy and current.

## What we've learned

- **LLM / prompts:** _(e.g. "balanced tier handles the analysis fine; fast tier mislabels keys")_
- **Models & tiers:** _(which tier for which step, and why)_
- **Media (fal):** _(which model, what inputs matter, typical latency/cost)_
- **Storage / DB:** _(gotchas, naming, what worked)_
- **Surprises / dead ends:** _(things that didn't work, so you don't retry them)_

### 2026-06-06 — A dropped slice fails silently; offline tests can't see integration seams
Adding seasonality to the retrieved enrichment: every UNIT was green (extractor produced the
profile, cache stored it, tool read it) yet live the agent always saw "no seasonal data".
Cause: `trip_intelligence.enrich()` REBUILDS `TripEnrichment` from the per-role providers, and
the new slice wasn't threaded through — silently dropped, no error, no log line, and the LLM
gracefully narrated around the missing data, which made the plans LOOK season-aware (weather
advisories filled the gap). Two lessons:
1. When a function reassembles a struct field-by-field, ADDING a field to the struct isn't
   enough — grep for every constructor of that struct. Pydantic can't help: omitted optional
   fields are valid.
2. Offline tests pass ≠ feature works. The live scenario run caught BOTH real bugs (this one,
   and the system prompt's READY rule bulldozing the advisory's stop-and-wait). Scenario-driven
   live verification (docs/scenarios.md) is part of the definition of done for agent behavior.
Regression test pattern: monkeypatch the one fetch (`web_intelligence.gather`) and assert every
slice survives `enrich()` — see `test_trip_intelligence_offline.py`.

## Open questions

_(Things you still need to figure out.)_
