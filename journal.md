# Journal

This is the running trace of your thinking as you build. It's the most important
document in the project — more than any single piece of code.

**How to use it**
- Add an entry at *meaningful* moments: a decision (and **why**), something you
  learned, a dead end you backed out of, a milestone reached.
- **Not** every edit. Capture the thinking, not the keystrokes.
- Always **timestamp** with date **and** time. Newest entries go at the bottom.
- Both you and Claude should add entries.

Format:

```
## YYYY-MM-DD HH:MM — Short title
What you were trying to do, what you decided, and why. What you learned.
```

---

## 2026-05-29 12:00 — Project initialized from the agent starter
Cloned the starter. Next: fill in `docs/problem.md` (what can't I do today?) and the
"Your project" section of `README.md` (what am I building?). Then design before coding.

## 2026-06-01 15:09 — Decided to build TripOS on this starter (not the Next.js stack I'd specced)
Brought in a detailed product vision for **TripOS / Travel OS** — an AI travel-planning
consultant for India. The written vision specced Next.js + TypeScript + Supabase +
Anthropic API with heavy DDD/Clean-Architecture. But this folder *is* the Python
agent-starter (FastAPI/HTMX/OpenRouter/Neon/Railway). Chose to build on the starter
because: (1) it's already deployable on Railway, which is the V1 goal; (2) it's
beginner-friendly and its doc-driven method already gives the structure the vision wanted;
(3) it ships working AI/DB plumbing. Trade-offs accepted: server-rendered HTMX UI instead
of a React SPA; a password gate instead of per-user Supabase auth for now; Claude models
called **via OpenRouter** (`anthropic/claude-...`) instead of the Anthropic SDK directly.
Also dropping the enterprise DDD ceremony per this repo's "no needless abstraction" rule —
keeping the *modular/atomic* spirit, not the machinery.

Two product decisions locked with the user: **data strategy = hybrid** (a curated seed
dataset researched from the internet + a live weather API + Claude reasoning, not live
scraping per message); **scope = one region** (Kerala + Tamil Nadu hill stations: Munnar,
Thekkady, Kodaikanal, Wayanad, Yercaud). V1 prices are AI estimates; real driver/hotel
quotes + payments are V2.

Did Step 1 (problem.md + README goal). Next: Step 2 — user_stories, failure_modes,
scenarios (I'll draft, then the user reviews).

## 2026-06-01 15:40 — Drafted Steps 2 & 3 (design docs); two scope calls defaulted
Wrote `user_stories.md` (12 stories, both entry paths), `failure_modes.md` (12 modes;
core risk = a confident, plausible, *wrong* plan; hard rules incl. "never claim a booking
happened — V1 books nothing"), `scenarios.md` (Priya happy path + 7 edge cases that double
as the deploy test checklist), and `policy.md` (the agent's step-by-step rulebook → system
prompt). Two scope decisions the user didn't object to, so defaulted (revisit anytime):
**Trip Comparison deferred to V2** (keep V1 focused on planning one trip well), and **auth
= single shared password gate**, not per-user accounts. Key behavioral stance baked into
policy: prefer curated seed data over model memory for facts; label estimates with ranges;
ask one question at a time; cheap LLM tier while gathering info, smarter tier for the final
itinerary. Next: Step 4 — `architecture.md` (the atomic-module breakdown = the "Module
Registry" the user asked for).

## 2026-06-01 15:58 — Step 4: Module Registry (architecture.md) drafted
Broke TripOS into ~20 atomic modules across 7 layers (domain/data, intake/discovery,
evaluators, composers, orchestration, persistence/output, web), each with a typed in→out
and an "impl" tag (data / rule / LLM / API). Added the domain model (Pydantic types in
`models.py`, aggregate root = `TripPlan`) and the data-flow sketch. Key design calls:
(1) curated seed catalog ships as **versioned JSON in the repo**, NOT the DB — only
user-generated trips/messages/shares go in Neon (`tripos_trips/_messages/_shares`, plan
stored as jsonb for V1 simplicity). (2) The evaluators share a *convention* (score +
reasons + suggestions), deliberately NOT a base class — keeping to the repo's no-needless-
abstraction rule. (3) Per-module "README" = a docstring written when each module is built,
kept next to the code so it stays accurate for debugging. Defined a vertical-slice build
order: models+catalog+Munnar seed → feasibility+budget → attractions+itinerary → planner+
minimal chat web (first end-to-end) → evaluators+rest → store+modifier+review+export →
seed other 4 + Railway deploy. Next: Step 5 — env/keys + `agent-doctor`, then start
building module 1.

## 2026-06-01 16:25 — Setup green; built module 1 (models + catalog + Munnar seed)
Installed uv via Homebrew (0.11.17; CLAUDE.md pins 0.5.7 but newer is fine), `uv sync`
ok. `agent-doctor` all green on first try — OpenRouter ($100 limit), Neon (PG17,
pgvector), R2, and a GitHub remote (abs-xperiments/travel-os--v1) all live.
Built module 1: `tripos/models.py` (`TravelStyle` StrEnum, `Attraction`, `Destination`),
`tripos/data/munnar.json` (6 real attractions with duration/indoor/suitability/scores),
`tripos/catalog.py` (cached JSON loader + `list_destinations`/`get_destination`/
`get_attractions`), and `scripts/tests/test_catalog.py` (4 offline tests). ruff +
pyright clean, tests pass. Learned: ruff prefers `enum.StrEnum` over `(str, Enum)` on
3.12 (UP042). Note: unknown destination returns None — that's the data-layer half of the
"out of scope" failure mode. Next: module 2 — `feasibility` + `budget` (pure rules,
high value, easy to test).

## 2026-06-01 16:55 — Module 2: trip_feasibility_checker + budget_estimator + per-module READMEs
On the user's request, adopted a clearer convention: **each module is a descriptively-named
folder** (`destination_catalog/`, `trip_feasibility_checker/`, `budget_estimator/`) with code
in `__init__.py` and a **plain-English README.md** (purpose + step-by-step + how to debug),
so a non-technical person can navigate and debug. Restructured module 1 to match (data now
lives inside `destination_catalog/data/`) and committed it on a new branch `build/tripos-v1`
(kept `main` clean). Built module 2, both pure/deterministic (no AI, no network):
- `trip_feasibility_checker.check_feasibility(attractions, days)` → required vs usable hours
  (8h/full day; arrival+departure days partial), verdict + reasons + fix suggestions (add N
  days / drop M lowest-worth stops). Tunable constants up top.
- `budget_estimator.estimate_budget(breakdown, budget?)` → total + low/high range (per-category
  uncertainty; accommodation ±20% is widest), confidence 50–95 from relative spread, and an
  over/under-budget note. Range-not-point is deliberate honesty (V1 prices are estimates).
Added `FeasibilityResult` / `BudgetBreakdown` / `BudgetEstimate` to models.py. 12 tests pass,
ruff + pyright clean. Next: module 3 — `attractions` (pick + cluster) and `itinerary` (build
the day-by-day), which gets us to a real Munnar plan.
