# Performance Optimization — Analysis & Comparison (branch `performance-optimization-v1`)

> Status: implemented on a branch + deployed to a **preview** service. Production is untouched.
> Nothing committed/pushed/merged — awaiting approval.

## 1. Latency breakdown (measured, uncached)

| Stage | Time | Notes |
|---|---|---|
| `resolve` (destination) | ~50s | geocode (~1s) + web research (Perplexity) + extraction (Sonnet) |
| `enrich` (stays/restaurants/weather) | ~47s | web research + extraction (one cached fetch serves all three) |
| `plan` (attractions/itinerary/budget) | **0.005s** | pure, deterministic — not a bottleneck |
| **Single trip total (uncached)** | **~98s** | resolve + enrich ran **sequentially** |
| **2-leg circuit total (uncached)** | **~154s** | legs ran **one after another** |

**Bottleneck = sequential I/O**, not model choice or planning logic. The planning maths is
instant; the wall-clock is web research + extraction, executed serially.

## 2. Optimizations (architecture only — no quality change)

1. **Parallel `resolve` + `enrich`** (`trip_intelligence.resolve_and_enrich`): enrichment is
   keyed by the destination slug and its research only needs the name, so it runs concurrently
   with resolve instead of waiting for it. Identical results.
2. **Parallel circuit legs** (`circuit_planner`): all legs are planned with `asyncio.gather`
   and stitched back in travel order — a circuit takes ~one leg's time, not the sum.
3. (Each leg also uses the parallel resolve+enrich, so concurrency compounds.)

No models changed, no retrieval removed, no features dropped, planning logic untouched.

## 3. Before/After (same prompts, caches cleared = worst case)

| Scenario | Before | After | Speedup |
|---|---|---|---|
| Single destination (uncached) | 98s | **58s** | ~1.7× |
| 2-leg circuit (uncached) | 154s | **53s** | **~2.9×** |

A 3–4 leg circuit improves even more (it collapses toward a single leg's latency).
**Cached** destinations were already fast and remain so.

### Quality check (identical outputs)
- Single (Pondicherry): resolved ✓, **9 stays**, **8 restaurants**, weather ✓.
- Circuit (Hampi→Gokarna): **both legs** built, continuous days, stay per leg, one per-person budget.
- 37 offline tests pass; `ruff` + `pyright` clean.

## 4. Notes / further options (not done)
- Concurrency is uncapped; up to ~`MAX_LEGS`×2 simultaneous calls on a big circuit. Could add
  a semaphore if a provider rate-limits. Fine at current scale.
- Could merge the two web searches (destination + enrichment) into one to cut a call — saves
  cost more than latency (parallelism already hides it). Deferred.

## 5. Safety / rollback
- All changes are on branch `performance-optimization-v1`, **uncommitted**.
- Preview runs on a **separate** Railway service (`tripos-web-preview`); production
  `tripos-web` is unchanged.
- Rollback = discard the branch / working changes. No manual recovery needed.
