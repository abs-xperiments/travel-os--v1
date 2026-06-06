# Architecture — TripOS Module Registry

**Stage 5 — Break it into atomic modules.**

Each module does **one thing**, has a typed input → typed output, and can be **tested in
isolation** (stage 6) before we compose them (stage 7). We build a thin vertical slice
end-to-end first — not all 20 modules before anything runs.

A note on style: the original vision asked for heavy DDD / interfaces / dependency
inversion. We're deliberately **not** doing that (this repo's rule: *no needless
abstraction*). "Modular" here means small, single-purpose files with clean typed
boundaries — not layers of indirection.

---

## Core data types (the domain model)

These live in `tripos/models.py` (Pydantic). They are the contracts every module shares —
get these right and the modules mostly fall out.

- **`TripBrief`** — start_city, days, dates?, group_type, budget, interests[], pace, food_pref, destination? *(what the user wants)*
- **`Destination`**, **`Attraction`** — the curated facts: name, region, duration, suitability flags (family/seniors/kids), photography/adventure level, indoor/outdoor, base/cluster, price baselines.
- **`TransportOption`**, **`Stay`**, **`FoodPlan`** — composer outputs, each with an estimated cost.
- **`DayPlan`**, **`Itinerary`** — the day-by-day schedule.
- **`BudgetEstimate`** — per-category amounts, total, **range**, confidence.
- **`SeasonAssessment` / `CrowdEstimate` / `WeatherImpact` / `FeasibilityResult` / `FatigueEstimate` / `ConfidenceScore`** — evaluator outputs. They share a shape: **score + reasons[] + suggestions[]** (a convention, not a base class).
- **`TripPlan`** — the aggregate root: brief + transport + stays + food + attraction clusters + itinerary + budget + the intelligence badges. This is what we persist, render, and export.

---

## The pieces

Grouped by layer. **Impl** column = how the "intelligence" is produced: **data** (read seed
data), **rule** (deterministic Python), **LLM** (model reasoning/phrasing), **API** (live
external), or a hybrid.

### A. Domain & data
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `models` | define shared typed contracts | — → Pydantic types | — |
| `catalog` | read the curated seed dataset | query → `Destination`/`Attraction`[] | data |

### B. Intake & discovery
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `profile` | build & validate the brief from chat | user answers → `TripBrief` | LLM + rule |
| `destinations` | recommend where to go | `TripBrief` (no dest) → ranked suggestions + reasons | rule + LLM |

### C. Intelligence / evaluators *(shared shape: context → score + reasons + suggestions)*
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `seasonality` | rate the season for a destination/month | (destination, month) → `SeasonAssessment` | data + rule + LLM |
| `crowd` | estimate crowd + best visit time | (place, date) → `CrowdEstimate` | data + rule |
| `weather` | weather impact for the actual dates | (destination, dates) → `WeatherImpact` | API + fallback |
| `feasibility` | **reject unrealistic plans** | (selected attractions, days) → `FeasibilityResult` | rule |
| `fatigue` | estimate effort (walking/travel) | (day plan/itinerary) → `FatigueEstimate` | rule |
| `confidence` | overall trip confidence % | `TripPlan` → `ConfidenceScore` | rule (aggregates the others) |

### D. Composers
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `attractions` | pick + cluster attractions | (destination, `TripBrief`) → clustered `Attraction`[] | rule + LLM order |
| `transport` | propose how to get there | (start_city, destination, group, budget) → `TransportOption`[] | data + rule |
| `accommodation` | propose stays per base | (clusters, nights, budget, group) → `Stay`[] | data + rule |
| `food` | plan meals + cost | (destination, food_pref, days) → `FoodPlan` | data + rule |
| `itinerary` | build the day-by-day schedule | (clustered attractions, days, hours, pace, mobility) → `Itinerary` | rule + LLM polish |
| `budget` | total it up with a range | `TripPlan` → `BudgetEstimate` | rule |

### E. Orchestration
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `planner` (the agent) | drive the policy end-to-end | conversation → `TripPlan` | LLM (pydantic-ai Agent; composers/evaluators are its tools) |
| `modifier` | apply a natural-language change | (`TripPlan`, "make it cheaper") → updated `TripPlan` + what-changed | LLM intent → targeted recompute |

**Intent-first orchestration (V2 Intelligence Upgrade, 2026-06-06).** The planner agent is
no longer a single trip-planning workflow: its system prompt classifies each message's
**intent** (FIND_STAYS / FIND_RESTAURANTS / DISCOVER_DESTINATIONS / PLAN_TRIP /
GENERAL_ADVICE) and routes via intent-scoped tools. There is deliberately **no separate
pre-classifier LLM call** — the agent itself is the router (zero extra latency/cost; one
source of truth). New tools alongside `build_trip`/`build_circuit`/`discover_circuits`/
`check_travel_season`:

| Tool | Intent | Reuses |
|------|--------|--------|
| `find_stays` | FIND_STAYS | the cached destination enrichment (`trip_intelligence.enrich`) — same cache key a later `build_trip` hits |
| `find_restaurants` | FIND_RESTAURANTS | same cached enrichment |
| `suggest_destinations` | DISCOVER_DESTINATIONS | `research()` + extraction, mirroring `circuit_discovery` |

A dynamic instruction injects **today's date** each run (the Travel Context Engine), so
relative dates ("today", "next weekend", "this December") resolve without questions.
`src/agent/agents/tripos_planner.py` is split into a package (`prompt` / `tools` / `recommend` /
`compact` / `streaming` / `agent` / `progress`) to stay under the 500-line file cap; its public
import surface is unchanged.

**Responsiveness (2026-06-06).** Three mechanisms, no quality change:
- **In-flight coalescing** — concurrent fetches for the same destination share one task
  (`web_intelligence.gather`, `destination_intelligence.resolve`), so a background prewarm and a
  build never pay for the same retrieval twice.
- **Prewarming** — `check_travel_season` (which the agent calls between gathering and building)
  already warms the enrichment cache; it now also fires a background destination resolve. By the
  time the traveler answers the last question, both caches are warm and the build turn is fast.
- **Live progress checklist** — `progress.py` (a per-turn Reporter behind a ContextVar) lets
  tools report honest stages; `stream_reply` races the agent-run iterator against the progress
  queue so ✓-checklist status events stream to the UI *while* a tool runs. Domain modules stay
  agent-agnostic via optional `on_progress`/`on_leg_done` callbacks.

**Voice input (2026-06-06)** — browser Web Speech API in `chat.html` only (feature-detected, no
backend): transcription appends into the chat input (never replaces, never auto-sends), so voice
is a drafting tool, not a command channel.

**Questionnaire-first gathering (2026-06-07).** PLAN_TRIP with missing essentials renders ONE
structured form block in chat instead of drip-fed questions. Division of labour: the **agent
analyzes** (decides what's known vs missing — it owns inference) and calls
`request_trip_details(known, missing, style)`; **deterministic code owns the UI** — a question
bank (`questionnaire.py`) maps validated field names to question specs (unknown names dropped
harmlessly), assembles the form JSON, fires the destination prewarm (retrieval hides inside
form-filling time), and pushes a `kind="form"` piece down the same per-turn channel the progress
checklist uses (the channel now carries `StreamPiece`s — see `pieces.py`). The browser renders
chips/inputs with conditional branching and a live "my understanding" review strip; submit
composes a readable message through the normal chat path, so the conversation stays the single
source of truth (persistence free, advisories unchanged, no new TripBrief fields). CLI gets a
text-bullet fallback automatically (no active channel).

**Split extraction (2026-06-07).** Enrichment keeps ONE research call but extracts the four
slices (stays / restaurants / weather / seasonality) in PARALLEL with small focused extractors
instead of one monolithic structured output — wall-clock ≈ the slowest slice. The season check
awaits only the seasonality slice; the rest finish in the background into the same cache entry.

### F. Persistence & output
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `store` | save/load trips + conversation | `TripPlan`/messages ↔ DB | db |
| `export` | PDF / shareable link | `TripPlan` → file / share slug | rule |

### G. Web / UX
| Module | Does one thing | Input → Output | Impl |
|--------|----------------|----------------|------|
| `web` | routes + HTMX screens, password gate | HTTP ↔ HTML fragments | FastAPI + Jinja2 + HTMX |

---

## Which starter services does each use?

- **`llm`** — `profile`, `destinations`, `attractions` ordering, `itinerary` polish, `planner`, `modifier`. Cheap tier while gathering info; smart tier for the final itinerary.
- **`db` (Neon)** — `store` only (trips + conversation messages + share links).
- **`research()` (web)** — sparingly, inside evaluators/composers to fill a genuine gap not in the seed data.
- **`media` / `storage` (R2)** — not needed for V1 core; only if we later persist exported PDFs.
- **External weather API** — `weather` module (new, small client; falls back to seasonal norms if down).

---

## Data flow

```
user chat
  → planner (agent)
      → profile ........................ TripBrief
      → [if no destination] destinations  → user picks one
      → attractions (+cluster)
      → transport / accommodation / food
      → itinerary
      → evaluators: seasonality, crowd, weather, feasibility, fatigue
      → budget  → confidence
  → TripPlan ──→ web review screen (one screen, per-section "why" + Modify)
                   │
       "make it cheaper" → modifier → re-runs only affected composers + budget + confidence
                   │
       Generate    → itinerary (final day-by-day)
                   → store (save)  → export (PDF / share link)
```

## Data you store

Seed catalog (destinations + attractions) is **not** in the DB — it ships as **versioned
JSON in the repo** (`tripos/data/*.json`). Reasoning: it's small, static, easy to edit and
diff, and trivially testable; no migrations for content edits. The DB holds only
**user-generated** data:

| Table | Columns (sketch) |
|-------|------------------|
| `tripos_trips` | `id uuid pk`, `created_at`, `updated_at`, `status text`, `brief jsonb`, `plan jsonb` |
| `tripos_messages` | `id bigserial pk`, `trip_id uuid → tripos_trips`, `role text`, `content text`, `created_at` |
| `tripos_shares` | `slug text pk`, `trip_id uuid → tripos_trips`, `created_at` |

One numbered migration per change (`migrations/001_create_tripos.sql`, …), applied via
`db.apply_migrations()`. `plan`/`brief` stored as `jsonb` so V1 stays simple — we
normalize into columns only if/when we need to query inside them.

---

## Proposed folder layout

**Naming & README convention:** each module is a **clearly-named folder** (a layman can
read the folder list and know what each does), holding its code in `__init__.py`, a
plain-English **`README.md`** (purpose, what it does step by step, and how to debug it),
and any data it owns. Shared types live in one `models.py` — the common vocabulary every
module speaks (not a behavioral module, so no folder of its own).

```
src/agent/tripos/
  models.py                         # shared domain types (the common vocabulary)
  destination_catalog/              # the trip-facts library   (__init__.py + README.md + data/)
  trip_feasibility_checker/         # "do these places fit the days?"   (+ README.md)
  budget_estimator/                 # itemised total + a likely range   (+ README.md)
  ...                               # one folder per module below, each with its own README.md
src/agent/agents/tripos_planner.py  # the orchestrating Agent
migrations/                         # numbered SQL
scripts/tests/                      # one test_<module>.py per module
```

The descriptive folder names below replace the short labels in the tables above as each
module is built (`catalog` → `destination_catalog`, `feasibility` → `trip_feasibility_checker`,
`budget` → `budget_estimator`, etc.).

---

## Recommended build order (stage 6 → 7)

Build a **thin vertical slice first**, then widen:

1. `models` + `catalog` + seed data for **one** destination (Munnar) — the foundation.
2. `feasibility` + `budget` — the cheapest, highest-value "smart" bits; pure rules, easy to test.
3. `attractions` + `itinerary` — produce a real day-by-day for Munnar.
4. `planner` agent wiring + a minimal chat `web` screen — **first end-to-end run**.
5. Layer in evaluators (`seasonality`, `crowd`, `weather`) and the rest of the composers.
6. `store` + `modifier` + review screen + `export`/share.
7. Seed the other 4 destinations; deploy to Railway; run the scenarios.
