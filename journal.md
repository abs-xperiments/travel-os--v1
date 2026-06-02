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

## 2026-06-01 17:30 — Module 3: attraction_selector + itinerary_builder (first real plan!)
Built the two composers that turn facts into a plan, both deterministic:
- `attraction_selector.select_attractions(destination, brief)` → scores stops by
  worth + interest match, **hard-filters out group-unsuitable stops**, greedily keeps the
  best while `trip_feasibility_checker` says it still fits, then orders by base + time of day.
- `itinerary_builder.build_itinerary(destination, stops, days, pace)` → packs ordered stops
  into days (8h/full day, arrival+departure half, pace factor), labels arrival/departure,
  never drops a stop silently. Reuses feasibility's hour constants (one source of truth).
Added `TripBrief` (+ GroupType/Pace/FoodPref enums), `DayPlan`, `Itinerary` to models.
**Bug caught by an end-to-end smoke run** (not by a unit test): with a soft scoring penalty,
a `family_with_seniors` trip still picked Eravikulam NP (marked not senior-suitable) and put
it on the tiring arrival day. Fix: made senior/child suitability a **hard filter**
(`_suits_group`), since comfort for seniors/kids is a core promise the score must not
override. Added a regression test asserting Eravikulam is excluded for seniors. Lesson:
unit tests passed, but composing the modules and *looking at the output* found the real
issue — keep doing smoke runs. 25 tests pass, ruff + pyright clean. The deterministic core
now produces a full Munnar day-by-day. Next: module 4 — the AI `planner` (an Agent that
calls these as tools) + a minimal chat web screen = first end-to-end with the LLM.

## 2026-06-01 18:10 — Module 4: the AI planner agent — FIRST LLM END-TO-END WORKS
Split module 4 in two: (1) `tripos/trip_planner` — a deterministic `plan_trip(brief)` that
runs catalog→select→itinerary→budget→feasibility into one `TripPlan` aggregate (testable
with no LLM); (2) `agents/tripos_planner.py` — the pydantic-ai Agent (build_model("balanced")
= Sonnet) whose system prompt is the condensed policy.md, exposing `list_destinations` and
`build_plan` as `tool_plain` tools. Rewrote `main.py` into a chat REPL (`uv run agent`).
Budget uses PLACEHOLDER baselines in trip_planner (clearly flagged; transport/accommodation/
food composer modules will replace them). Added `TripPlan` to models.
**Live smoke run (Priya's request) verified the core claim:** the LLM called `build_plan`,
and the returned itinerary + budget range (₹27,075–₹36,925) exactly match our modules'
output — no hallucinated stops or prices. Seniors filter held live (Eravikulam excluded);
agent labeled prices as estimates and said it books nothing (failure_modes rules honored).
32 offline tests pass (agent tools tested directly, no API spend), ruff + pyright clean.
Learned: register tools via `agent.tool_plain(func)` so the funcs stay importable/testable
without paying for a model call. Next: module 5 — the web UI (FastAPI + HTMX chat + review
screen, password-gated) so it's usable in a browser, then persistence/export, then deploy.

## 2026-06-01 18:40 — SCOPE CHANGE: destination-agnostic, nationwide (India)
User reversed the earlier "one region" scope: TripOS must be **destination-agnostic** and
plan for any valid Indian destination, with knowledge **data-driven and extensible** (adding
a destination must need NO code change). Good news: our planning engine was already agnostic
— `attraction_selector`/`itinerary_builder`/`feasibility`/`budget`/`trip_planner` have zero
destination-specific logic; the catalog globs every `*.json`, so a destination IS just data.
Work done:
- De-hardcoded the only two region mentions (agent system prompt + CLI greeting → "across
  India", rely on `list_destinations`). Updated scope lines in README/policy/user_stories/
  failure_modes/scenarios (Munnar/Priya remain as *illustrative* examples per the user).
- Ran a **Workflow** (user invoked "workflow"): 23 agents (Sonnet) in parallel, one per
  destination across all regions (N/S/E/W/Central + Andaman), each returning a schema-
  validated `Destination` (6–11 real attractions, hidden gems, honest suitability). ~3 min,
  ~201k tokens. Imported all 23 via `Destination.model_validate` → one JSON file each in
  `destination_catalog/data/`. Catalog now = **24 destinations**.
- Smoke-tested planning (no LLM) for Goa/Leh-Ladakh/Jaipur/Darjeeling — all feasible; Leh
  seniors plan correctly drops high-altitude/strenuous stops. Fixed 2 tests that used "goa"
  as the out-of-scope example (now covered) → switched to "paris" (international = out of
  scope; TripOS is India-only). 32 tests pass, ruff + pyright clean.
HONESTY NOTES: the seed data for the 23 new destinations is AI-drafted (reviewable JSON, not
runtime hallucination) — durations/ratings are estimates and should be spot-checked over
time. Transport/budget baselines are still a FLAT placeholder (Delhi→Ladakh costs the same
as Delhi→Goa today) — distance-aware costs come with the transport composer module.
OPEN OPTION: a runtime provider that auto-generates+caches data for a destination not yet in
the catalog (truly "any destination" without pre-seeding). Deferred; current design already
satisfies "add a destination = add data, no code change". Next: module 5 — the web UI.

## 2026-06-01 19:20 — Module 5: web UI (browser chat), end-to-end verified
Built `src/agent/tripos_web.py` (FastAPI) + `src/agent/templates/` (base/chat/_turn/login),
reusing the starter's `examples/agent_idea_web` pattern: Jinja2 + HTMX + Tailwind + marked,
all via CDN, no JS build. It's a CHAT UI (not the example's one-shot pipeline): POST /chat
runs the SAME `planner_agent` from the CLI and returns user+assistant bubbles as an HTMX
fragment appended to the log; assistant markdown is rendered client-side by marked (user text
stays escaped — no injection). Conversation history is IN MEMORY per session cookie for now
(`_SESSIONS` dict) — the persistence module will move it to Neon. Reused the APP_PASSWORD
gate + /login from the example. Routes: /, /chat, /reset, /login.
Verified live against a running server (port 8123): GET / → 303 to /login (gate works, user
has APP_PASSWORD set) → logged in → POST /chat for a Coorg trip returned a full plan with
real stops (Abbey Falls, Pushpagiri, Talacauvery), our exact budget range (₹17,355–₹23,445),
estimates labeled, rendered as markdown. Whole chain browser→agent→tools→modules→HTML works.
ruff + pyright clean. NOTE: railway.toml still points at the example app — switch it to
`fastapi run src/agent/tripos_web.py` in the deploy step. Next: module 6 — persistence
(Neon: tripos_trips/_messages/_shares) so chats/trips survive restarts + can be saved/reopened,
then export/share, then Railway deploy.

## 2026-06-01 20:05 — Module 6: persistence (trips saved/reopened in Neon)
Built `tripos/trip_store` (+ migration `001_create_tripos.sql`, + README). Simplified the
schema vs the plan: ONE table `tripos_trips` — a trip IS its conversation, and its id (uuid
hex) doubles as the shareable URL, so no separate messages/shares tables needed for V1. Each
trip stores `transcript` jsonb ([{role,content}] for display) AND `agent_messages` jsonb
(pydantic-ai history via `result.all_messages_json()` ↔ `ModelMessagesTypeAdapter.validate_json`)
so the AI continues with full context after a restart. Verified the serialization API in the
installed pydantic_ai 1.104 before using it. Functions: init_db / ensure_trip / get_trip /
load_agent_messages / append_turn / list_recent.
Rewired `tripos_web.py`: lifespan applies migrations on startup + closes the pool; replaced
the in-memory `_SESSIONS` with trip_store; added GET /trip/{id} (reopen + share link) and GET
/trips (saved-trips dashboard); session cookie now holds the trip id. Templates: chat.html
renders saved transcript (for/else → greeting when empty) + "Saved trips" link; new trips.html.
Verified: trip_store integration test passes against real Neon (create→append→reopen→list,
with cleanup); web boots with the new lifespan, login + GET / + GET /trips all 200. First
integration run hit a transient Neon cold-start TLS ConnectionReset — retry passed; the
starter's own db test showed the same ~33s cold start, so it's environmental, not a bug.
32 offline + 1 integration test pass, ruff + pyright clean. Known: GET / creates an empty
trip row per fresh visit (dashboard hides empty ones via jsonb_array_length>0). Next: module
7 — export (PDF) + polish the share flow; then module 8 — Railway deploy (switch railway.toml
startCommand to `fastapi run src/agent/tripos_web.py`, set APP_PASSWORD + keys as Railway vars).

## 2026-06-01 20:35 — Module 7: PDF export (print view, dependency-free)
Chose a **print-optimized HTML page + browser "Save as PDF"** over a server-side PDF library.
Rationale: the plan lives as the assistant's markdown in the transcript; a print view reuses
the same marked renderer (tables/headers intact), adds ZERO dependencies, and avoids fragile
Docker/system libs (weasyprint) or worse output (xhtml2pdf) right before the Railway deploy.
The user clicks "Save as PDF" → real PDF, filename = the <title> (trip title). Added:
- GET /trip/{id}/print → `print.html` (standalone light-theme printable doc; @media print hides
  the toolbar; renders transcript, user prompts as light context, assistant markdown as body).
- "📄 PDF" link in the chat header (shown once there's a transcript) and per-trip on /trips.
- Passed trip_id into chat.html.
Verified live: seeded a trip row (no LLM), GET /trip/{id}/print → 200 with the "Save as PDF"
button and the plan content; markdown table renders in-browser (same path as chat). Cleaned up
the seeded row. ruff + pyright clean, 32 offline tests pass. NOTE for deploy: if a true
one-click server-generated .pdf is ever wanted, revisit with a pure-python lib. Next: module 8
— Railway DEPLOY (the V1 finish line).

## 2026-06-01 21:10 — Module 8: DEPLOYED TO RAILWAY — V1 IS LIVE 🚀
TripOS V1 is live at https://tripos-web-production-4f1c.up.railway.app (gated by APP_PASSWORD).
Steps: pointed `railway.toml` startCommand at `fastapi run src/agent/tripos_web.py`; created
Railway project `tripos-v1` + service `tripos-web` via `railway add --service tripos-web -v ...`
with the three needed secrets (OPENROUTER_API_KEY, DATABASE_URL, APP_PASSWORD) pulled from
.env — only those three are required (config.py: openrouter required; db_url/app_password
optional in config but needed by our app; FAL_KEY/R2_* unused by TripOS so skipped). `railway up
--detach` built the Dockerfile image; `railway domain` assigned the URL.
VERIFIED IN PROD: gate 303 → login 303 → authed home 200 → a live /chat planned a full Coorg
trip with our exact catalog data + budget range and "estimates" labeling. This confirms the
seed JSON + templates ARE in the deployed image (uv's editable install resolves them under
/app/src), and OpenRouter + Neon both work in the container — my earlier worry about data files
missing from the image was unfounded.
Notes/gotchas: Railway's backboard GraphQL API timed out twice (railway init, railway add) but
the operations LANDED server-side (project/service + vars confirmed via `railway list` and
`railway variables --json` keys) — retry/verify, don't assume failure. Already logged in as
abirami.moa@gmail.com so no interactive login was needed. railway.toml committed.
ALL 8 STEPS DONE — V1 SHIPPED. Work is on branch `build/tripos-v1` (main untouched; can merge/
push to GitHub when ready). Day-2: `railway up` to redeploy, `railway logs` to debug,
`railway variables --set` to change secrets. Possible next: spot-check the 23 AI-drafted
destination datasets; distance-aware transport/budget (transport composer); runtime fallback
for un-seeded destinations; V2 (driver quotes/bookings/payments).

## 2026-06-02 — Streaming responses (SSE), ChatGPT-style
Replaced the blocking POST /chat (returned the full reply at once) with streaming. Key
learning: for a TOOL-CALLING agent, pydantic-ai's `run_stream()` only streams the FIRST
model turn (the preamble) and misses the plan written AFTER build_plan runs. Verified this,
then switched to `agent.iter()` + per-node `node.stream(run.ctx)`, extracting text from
PartStartEvent(TextPart)/PartDeltaEvent(TextPartDelta) — this streams EVERY model step
(preamble status lines + the final plan). Added `stream_reply()` (+ `StreamPiece`) to
agents/tripos_planner.py (keeps streaming logic with the agent, testable); web layer just
frames SSE. New route POST /chat/stream → `text/event-stream`, events `data:{"t":delta}` …
`data:{"done":true}` (errors `data:{"error":..}`); persists the turn via append_turn on
'done' using run.result.all_messages_json(). Frontend: chat form now a small vanilla-JS
fetch+ReadableStream handler that parses SSE, appends deltas, re-renders markdown live
(marked), shows a ▍ typing cursor, AbortController cancels the prior stream when a new
message is sent, and a catch handles dropped connections. Removed the old /chat route +
_turn.html. SSE headers Cache-Control:no-cache + X-Accel-Buffering:no to avoid proxy
buffering. Verified live locally: first token immediate, chunks stream continuously, done
event fires, out-of-scope handling works mid-stream, markdown preserved. ruff+pyright clean,
32 tests pass. Redeployed to Railway (railway up --detach, ~140s) and VERIFIED streaming
in prod: live /chat/stream emits incremental `data:{t}` chunks then `done`; a Hampi plan
streamed token-by-token with its markdown table intact. Shipped. Branch pushed to GitHub.

## 2026-06-02 — V2 Phase 1: provider-agnostic retrieval (plan ANY destination)
Big architecture step (design in docs/V2_ARCHITECTURE.md, from a 9-agent workflow). User
mandate: the catalog is a CACHE, never a gatekeeper — no "supported destinations" concept.
Built in 4 tested, committed increments, each green:
- 1A: `provider_interfaces` (DestinationProvider Protocol + slugify), `provider_registry`
  (swappable, priority-ordered — the seam for future paid providers), `providers`
  (CatalogDestinationProvider = the 24 curated places as a fast cache provider). +Coordinates.
- 1B: `knowledge_cache` (Neon table `tripos_destination_cache`, migration 002; get(fresh)/put;
  wired into web lifespan) — retrieved places cached ~60d so we fetch once.
- 1C: retrieval core — `providers/geocoding.py` (Nominatim/OSM verifies existence + coords),
  `providers/destination_retrieval.py` (WebDestinationProvider: verify -> research()/Perplexity
  -> extract a structured Destination with Sonnet), `destination_intelligence.resolve()`
  (cache -> catalog -> web; None ONLY if unidentifiable). Destination gained optional
  country/coordinates. Verified live: Pondicherry -> 9 real attractions + cached; nonsense -> None.
- 1D: removed the gatekeeper — `trip_planner.plan_trip(brief, destination)` takes an injected
  Destination (no catalog lookup, no "unknown destination" raise); agent `build_plan` -> async
  `build_trip` that resolves ANY place then plans it; system prompt no longer claims a fixed
  list. Verified live: streaming a Pondicherry plan via the async tool + SSE = 255 chunks. The
  roadmap's riskiest item (async tool boundary under streaming) works.
KEY LEARNING: pydantic-ai `tool_plain` accepts ASYNC functions, so build_trip can `await`
retrieval and SSE streaming (agent.iter) still works. Phase 1 = 38 tests (32 offline + 6
integration), ruff+pyright clean. Next: deploy Phase 1 to Railway + verify a non-catalog
destination streams in prod. Then Phase 2 (stay-first + accommodation/restaurant/weather
intelligence behind the same provider interfaces) and Phase 3 (circuits + premium adapters).
DEPLOYED Phase 1 to Railway + VERIFIED IN PROD: a fully-specified request streamed a real
4-day **Bali** plan (Nusa Penida, Tanah Lot, Tegallalang, Pura Besakih) — international,
not in the catalog, retrieved live on https://tripos-web-production-4f1c.up.railway.app.
Branch pushed to GitHub. Phase 1 shipped.

## 2026-06-02 — Post-Phase-1 fixes (3 product issues)
Issue 1 (conversation dead-end): root cause = the model sometimes ends a turn with a "I'll
put that together" PROMISE and no build_trip tool call, so agent.iter completes with no plan.
Fix (2 layers): (a) strengthened the system prompt — "each turn do exactly ONE: ask ONE
question OR call build_trip; never promise-and-stop"; (b) deterministic guard in stream_reply
— track whether a tool was called this turn; if not AND the streamed text matches a narrow
PROMISE regex (won't match questions), auto-continue ONCE with a forced "call build_trip now"
nudge so the plan lands in the SAME response (no extra user prompt). Verified the regex
matches promises but not questions (offline test).
Issue 2 (blank during planning): the silent gap was build_trip executing (geocode+research+
extract) with no tokens streaming. Fix using the EXISTING SSE (not a rebuild): stream_reply
emits a kind="status" piece the moment a build_trip tool call starts; chat_stream maps it to
`data:{status}`; chat.html shows it as a transient dimmed progress note ("Building your trip…
• Retrieving destination intelligence • Selecting stops • Optimising route • Estimating
budget") that's replaced when plan tokens arrive. Verified live: status fires once, plan
streams in one turn with real Munnar stops.
Issue 3 (India-only copy): updated GREETING to "...anywhere in the world 🌍", input placeholder,
and added example-prompt chips (domestic + international: Kerala/Japan/Bali/Vietnam/Europe/
family) shown on a fresh chat; clicking a chip sends it. Copy/positioning only — no layout
redesign. (System prompt already said worldwide since Phase 1D.)
32 offline tests pass, ruff+pyright clean. DEPLOYED + VERIFIED IN PROD: new greeting
"anywhere in the world" + example chips live; a live stream emitted 1 status event then the
plan in one turn with a done event. All 3 issues fixed on the live URL.

## 2026-06-02 — Per-person budget throughout
Made per-person the primary budget unit end-to-end. Changes: TripBrief.budget is now PER
PERSON (+ optional `travelers`); BudgetEstimate redefined to per_person_total / per_person_low
/ per_person_high + travelers + group_total (was total/low/high). budget_estimator totals
PER-PERSON, scales by travelers for group_total, and checks the per-person budget. trip_planner
baselines reworked to per-person (accommodation assumes ~2 share a room) + `traveler_count()`
(uses brief.travelers else inferred from group: solo1/couple2/friends3/family4). Agent:
build_trip gains a `travelers` param; system prompt now asks for the PER-PERSON budget + number
of travelers, and presents budget as a per-person range labelled "per person" plus the group
total when known; _compact_plan exposes per_person_budget (primary) + travelers + group_total.
Updated budget tests. Verified live: Munnar 3d family budget₹15k/pp, travelers 4 → per-person
est ₹16,100 (range 13,755–18,445), group total ₹64,400 (=×4). 35 offline tests pass, ruff+
pyright clean. Next: deploy + verify in prod.

VERIFIED IN PROD: a Munnar plan rendered a budget table "Per Person | Group of 4" — per-person primary + group total, live.

## 2026-06-02 — V2 Phase 2: accommodation + restaurant + weather intelligence
Added the "stay/eat/weather" intelligence layer behind the provider-agnostic pattern (scoped:
single-destination enrichment + budget realism; multi-stay route optimisation stays with
circuits in Phase 3). New: models Accommodation/Restaurant/WeatherInsight/TripEnrichment +
optional stays/restaurants/weather on TripPlan; provider_interfaces WeatherProvider/
AccommodationProvider/RestaurantProvider; `intelligence_cache` (Neon, migration 003);
`providers/web_intelligence.py` = ONE cached combined research()+extraction per destination,
sliced by three thin providers (cost: one fetch serves all three); `trip_intelligence.enrich()`
(best-effort — empty on failure so the plan still ships). Integrated into build_trip: resolve →
enrich → use retrieved mid-tier nightly rate (trip_planner.per_person_nightly, ~2 share a room)
to refine the accommodation budget → attach stays/restaurants/weather → _compact_plan surfaces
them → prompt presents "Where to stay / eat / Weather" sections (chat + PDF already render the
markdown). Registered the 3 providers idempotently per role. Verified live (Munnar): 6 stays
(budget/mid tiers, e.g. ₹850–1500), 6 restaurants, weather seasons; per-person est shifted to
the retrieved rate. 37 offline tests pass (+ stay-override & per_person_nightly tests, +
integration test_trip_intelligence), ruff+pyright clean. Honesty: prices/ratings are web
estimates, not live bookings (labelled). Next: deploy + verify in prod.
