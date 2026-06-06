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

VERIFIED IN PROD: a Coorg plan rendered "Where to Stay (nightly estimates, not live bookings)" + restaurants + weather + per-person budget. Phase 2 live.

## 2026-06-02 — V2 Phase 3 (part 1): Circuit Discovery Engine
Added "I have N days in <region> — where should I go?" Behind the provider-agnostic pattern:
models Circuit/CircuitLeg/CircuitOptions; provider_interfaces CircuitProvider;
providers/circuits.py WebCircuitProvider (cached research()+extract via intelligence_cache key
"circuit:<region>:<nights>") with INTELLIGENT night allocation (model allocates nights/leg by
how much there is to do, not evenly); circuit_discovery.discover() (best-effort → [] on
failure); agent `discover_circuits` tool + prompt rule (region+days but no single place →
discover_circuits, present 2-4 routes, user picks, then build_trip the chosen base). Verified
live: Kerala 6 nights → 4 routes incl. "Classic Kerala Family Loop: Kochi→Munnar→Thekkady→
Alleppey→Kochi" nights [1,2,1,1,1] ~₹30k/pp. 37 offline tests + integration test_circuit_discovery,
ruff+pyright clean. SCOPED: auto-building the whole multi-stop circuit in one step (resolve +
enrich every leg → stitched multi-leg itinerary + combined budget) is deferred — it's ~8 web
calls per build (cost/latency in the stream), so for now circuits are recommended and the user
plans a chosen base via build_trip. Next: deploy + verify; then (optional) the multi-leg auto-build.

## 2026-06-02 — Conversational UX: hide all internal/system language
Consumer-facing voice fix (prompt-only; no architecture change). Restructured the agent
system prompt into a strict VOICE section (what the traveler sees) + a HOW-YOU-OPERATE section
(internal, never revealed). VOICE forbids any mention of tools/functions/parameters/"required
details"/"validation"/"the planner/system/workflow"/retrieval/DB/APIs, and gives explicit
bad→good phrasing swaps ("I can't infer your budget" → "What's your approximate per-person
budget?"; "I won't make up numbers" → just ask). Missing info → warm question or a short
bullet list, never a status update or a numbered form. Removed literal tool names from the
prompt body (described behavior instead) to cut leakage; the model still calls the tools via
their schemas. Synced docs/policy.md (Tone & style → Voice rule) and the module docstring.
Verified locally: a bare "I'd like to plan a trip" → a friendly bulleted set of questions with
ZERO forbidden terms. 37 offline tests pass, ruff+pyright clean. Next: deploy + verify in prod.

VERIFIED IN PROD: (voice) bare request -> friendly bulleted questions, zero internal jargon; (circuits) "6 days in Kerala" -> 4 named routes with nights. Both live.

## 2026-06-02 — V2 Phase 3b: multi-leg circuit auto-build (the deferred heavy piece)
Built the full multi-destination trip builder. New: models CircuitStop/CircuitPlan;
`circuit_planner.plan_circuit(name, legs, brief)` — for each (destination, nights) leg it
reuses destination_intelligence.resolve + trip_intelligence.enrich + trip_planner.plan_trip,
then stitches: continuous day numbering across legs (titles prefixed with the place), a stay
per leg, and ONE combined per-person budget via new trip_planner.circuit_budget (single base
transport + inter-city hop/leg + per-leg accommodation/food/activities). MAX_LEGS cap. Agent:
`build_circuit` tool (parallel destinations+nights lists) + _compact_circuit; prompt now says
"when they pick a route, build the WHOLE multi-stop trip" and present it leg by leg + one
combined per-person budget. Cost/latency: a resolve+enrich per leg (cached after first) — runs
behind the streaming "Building your trip…" status; not a separate background job. Verified live:
Munnar(2n)→Wayanad(1n) → days [1,2,3], a stay each leg, per-person ₹22,450 / group ₹44,900.
37 offline tests + integration test_circuit_planner (2 catalog legs). ruff+pyright clean.
Deferred still: deep geo route re-ordering + real inter-city times; premium provider adapters.
Next: deploy + verify in prod.

VERIFIED IN PROD: "Munnar 2n -> Wayanad 1n" -> full multi-stop circuit built leg by leg (both legs, per-leg stays, days 1-3, one per-person budget). Phase 3b live. V2 ROADMAP COMPLETE.

## 2026-06-02 — Perf optimization + planning-gate fix (APPROVED → shipping to prod)
PERF: bottleneck was sequential I/O (resolve ~50s THEN enrich ~47s; circuit legs one-by-one).
Fix = concurrency only (no model/quality change): trip_intelligence.resolve_and_enrich runs
resolve + enrich in parallel (enrich keyed by slug, research needs only the name); circuit_planner
plans all legs with asyncio.gather and stitches in order. Measured uncached: single 98s→58s
(~1.7x), 2-leg circuit 154s→53s (~2.9x); deterministic planning was always ~5ms. Quality
identical (9 stays/8 restaurants/both legs). Doc: docs/PERF_OPTIMIZATION.md. Previewed on a
separate Railway service (tripos-web-preview); prod untouched until approval.
GATING FIX: model was asking questions AND calling build_trip in the same turn (guessing missing
fields). Fix: explicit two-state rule in the prompt (GATHERING vs READY) — ask XOR plan, never
both; never guess required fields; skip-phrases ("you decide"/"no preference"/…) count as
answered; final check before building. ALSO refined the dead-end guard so it never force-builds
on a turn that asked a question (that guard could otherwise cause premature planning). Verified
locally: "Plan a 15-day trip to Dubai" now ASKS (no plan, no tool call); a complete request
builds. 37 offline tests pass, ruff+pyright clean. User approved both → commit, push, merge to
build/tripos-v1 + main, deploy to production.

## 2026-06-06 01:17 — Seasonality-aware planning: decisions + doc updates (stage 3–4)
New feature: treat the travel month as a planning dimension, not an itinerary footnote —
evaluate suitability BEFORE planning, advise on bad months (with better windows), respect the
user's final choice, and adapt the itinerary to the season (indoor/evening bias in heat or rain).
Decisions (user-approved):
1. GRANULARITY = month + optional exact dates. Seasonality is a month-level phenomenon and V1
   has nothing that can use day precision (no live forecasts, no booking). BUT exact dates the
   user volunteers are STORED on the brief as the extension point for V2 accommodation booking
   (Booking.com-style needs dates at *booking* time, not planning time) — schema ready, zero
   friction now, no migration later.
2. TRAVEL MONTH = required-but-skippable. The agent always asks "when are you travelling?";
   "flexible / not sure" counts as answered → TripOS recommends the best window and plans for it.
   (Optional would make the whole feature silent for most users.)
3. KNOWLEDGE SOURCE = retrieval, not model memory. Extend the EXISTING single research call +
   extraction to also produce a year-round 12-month suitability profile, cached per destination
   (cache stays destination-keyed; any month answered locally; zero extra web calls). A new
   check_travel_season tool lets the agent advise BEFORE build_trip; it warms the same cache the
   build uses, so total cost is unchanged — the fetch just happens earlier.
Failure-mode rule worth remembering: advisory is best-effort — if research can't confirm the
season is bad, do NOT bluff a warning (confident wrong advisory < none). Never block on season:
advise once, then respect the choice and adapt.
Stage 3–4 docs updated (user_stories 13–16, failure_modes rows + hard rule, 7 seasonality
scenarios incl. Dubai-in-July and span-two-months, policy step 4 "Assess the season" + Travel
Context in compose). Build order: models → retrieval profile → advisory tool + prompt →
season-adaptive plan_trip/attraction_selector → tests + live verify + deploy.
NOTED (not fixed here): policy.md/user_stories.md/scenarios.md still carry stale V1-region
language ("South Indian hill stations", Paris out-of-scope) that contradicts the shipped
worldwide V2 — needs its own doc-sync pass.

## 2026-06-06 01:25 — Trip Comparison promoted to V1, sequenced AFTER seasonality
User decided Trip Comparison (Plan A/B/C side by side) moves from "deferred to V2" into V1
scope. Sequencing decision (user-approved): finish + ship seasonality-aware planning first,
THEN design comparison as its own feature (its own stage 3-4 pass: what gets compared, chat-UX,
how plans are labelled/stored, side-by-side budget rendering). Why this order: (1) never two
half-built features at once; (2) the highest-value comparison — same destination across two
travel windows ("Dubai in July vs December") — literally requires seasonality to exist first.
User also fixed the stale one-liner in policy.md (dropped "South Indian hill stations").

## 2026-06-06 01:50 — Seasonality steps 3–5 built: retrieval profile, advisory tool, adaptive plans
One pass, all offline-green (48 tests). The shape that matters:
- RETRIEVAL: extended the EXISTING combined research call + extractor to also produce a
  12-month SeasonalityProfile (rating + note + lean_indoor per month, best_months). Zero extra
  web calls. Cache key versioned to "<id>:v2" — pre-seasonality prod cache rows would otherwise
  pin seasonality=None for up to 30 days; new key bypasses them, old rows age out via TTL.
- JUDGMENT vs MECHANICS split: the extractor LLM decides lean_indoor (does this month warrant
  sheltered plans? rain/heat yes, crowds no); deterministic code merely applies it
  (attraction_selector prefer_indoor = +2.5 soft bonus for indoor stops — bias, not ban).
- ADVISORY: new check_travel_season(destination, month?) agent tool → trip_intelligence
  .season_profile() → same cached gather(); advising BEFORE build costs nothing extra (the
  fetch just happens earlier; build then hits cache). month omitted = best-window mode for
  flexible travelers. System prompt gained the SEASON CHECK state (advise once on
  challenging/not_recommended then WAIT; no friction on acceptable+; never bluff on unknown)
  and travel month in the REQUIRED list ("flexible" counts as answered).
- ADAPTATION: plan_trip(..., season=) biases selection + stamps a "Planned for July travel —…"
  note on day 1 (visible in chat AND print/PDF). Circuits: each leg adapts to ITS OWN profile.
- STREAMING FIX while here: status note is now per-tool ("Checking the season…" vs "Building
  your trip…") and re-emits on CHANGE (chat.html replaces status text), so a season-check
  followed by a build in one turn shows honest progress.
Next: live verify the scenarios (Dubai-in-July advisory; Munnar-in-January no-friction), then
deploy with user approval.

## 2026-06-06 02:15 — Live verification caught two real bugs; both fixed; all scenarios pass
Offline-green code failed the live Dubai-in-July scenario TWICE, differently each time:
1. PROMPT CONFLICT: the READY rule ("build and present in the SAME reply") bulldozed the
   advisory's "STOP and WAIT" — model advised and built in one turn. Fix: an explicit ADVISING
   state — the advisory and the plan NEVER share a reply (same medicine as the old ask-vs-build
   bug), with the exception carved into the READY rule itself so the two can't fight.
2. DROPPED SLICE: trip_intelligence.enrich() rebuilds TripEnrichment from the per-role
   providers and silently dropped the new seasonality field — agent always saw "unknown",
   advisories were no-ops, lean_indoor never fired. The earlier "adapted-looking" Dubai plan
   was riding on weather advisories alone. Fix: a SeasonalityProvider role (interface +
   WebSeasonalityProvider + registry), enrich() carries the 4th slice; offline regression test
   monkeypatches gather() and asserts every slice survives. Lesson in docs/learnings.md.
Verified live after fixes: Dubai/July → advisory ONLY (best window Nov–Mar, one question, no
build) → "keep July" → immediate indoor/evening-adapted plan, Travel Context first, no
re-warning. Munnar/January → verdict "excellent", zero friction, builds in the same turn with
correct status progression ("Checking the season…" → "Building your trip…" — the new
status-on-change streaming). 50 offline tests, ruff+pyright clean. Remaining: deploy (needs
user approval) + prod smoke.

## 2026-06-06 02:40 — Seasonality SHIPPED to production
railway up → clean boot. Prod smoke via the live SSE endpoint: Dubai-in-July full brief →
"Checking the season and weather for your dates…" status, then an advisory-ONLY reply (extreme
heat, Nov–Mar + Oct recommended, one keep-or-shift question, NO plan built) — exactly the
designed ADVISING behavior, on the deployed URL. Prod + local share the Neon cache, so the
dubai:v2 / munnar:v2 profiles were already warm. Feature complete per docs/scenarios.md
§Seasonality. Next feature (user-decided order): Trip Comparison — own stage 3–4 design pass.

## 2026-06-06 03:05 — New spec: personalization + input friction + constraint adherence; re-sequenced
User feedback spec landed (3 streams): preferences as constraints (non-touristy → deprioritize
mainstream), hybrid input collection (compact upfront intake + adaptive follow-ups), and budget
as a HIGH-PRIORITY constraint (never ship ₹95k plan on ₹50k budget without warning). Audit
findings: budget today is a COMMENTATOR not a constraint (estimator appends a note; stay rate
always mid-tier; nothing economizes; circuits not budget-ranked). Personalization has NO
channel: interests = 9 enums (4 scored), no free-text prefs reach build_trip, Attraction has no
touristy/hidden dimension. Cached-enrichment caveat: extraction is colored by the FIRST
traveler's budget then cached 30d — per-traveler tailoring must live at selection/presentation.
DECISIONS (user): this spec BEFORE Trip Comparison (feedback-driven; comparison gets better
after); phase order A budget → B preferences → C structured intake. Phase A design: fit-first
(auto stay-tier downgrade when over budget — EXCEPT when interests include luxury), advisory
turn only if still over (reuse the seasonality ADVISING pattern), budget-compatibility-ranked
circuits. Levers are honest about placeholder baselines: stay tier + duration are the real ones.

## 2026-06-06 03:30 — Budget-trust spec folded into Phase A before any code (good timing)
Third user spec (budget accuracy/transparency/trust) arrived with Phase A designed but unbuilt
— merged into the design instead of becoming its own phase. Adds to Phase A: (1) ranges with
ROUNDED endpoints as the PRIMARY figure (live runs showed "₹18,835–₹25,715" — false precision);
(2) confidence = high/medium/low derived from the REAL knowledge state (month known? stay rates
retrieved vs placeholder?) + stated reason — replacing the spread-% which was confidence
theater; (3) a ✓/⚠/❌ Budget Feasibility verdict on every plan w/ suggested adjustments;
(4) HARD RULE: never an exact flight fare without a live source — the live Dubai run showed the
model quoting "₹8,000–18,000 return" FROM MEMORY, exactly the fabrication class banned (ranges
+ "typical patterns" wording only); (5) presentation contract (range+confidence+verdict) is
permanent — future distance-aware composers improve accuracy, not the format. Deterministic
thresholds chosen: fits = total ≤ budget; slightly_over = total > budget, low ≤ 1.4×budget;
not_achievable = low > 1.4×budget. Endpoints rounded to ₹500 (floor low, ceil high).

## 2026-06-06 04:05 — Phase A built & live-verified: budget is now a constraint, honestly presented
Engine: budget_estimator rewritten — per-person RANGE with rounded endpoints (floor/ceil to
₹500) is the primary figure; confidence = high/medium/low from REAL knowledge flags
(month_known, stays_retrieved) + stated reason (replaced the spread-% which was confidence
theater); three-state fit verdict (fits / slightly_over / not_achievable at low>1.4×budget)
with matching levers; month-unknown widens every band 1.5×. trip_planner.choose_stay() does
fit-first economizing: highest tier affordable from what's left per night after other costs
(_EST_STOPS_PER_DAY=2 rough), luxury NEVER silently downgraded below mid — conflict flagged
for the agent to ASK. Circuits: per-leg choose_stay against the WHOLE-trip budget; flags into
circuit_budget. Agent: compact plans expose range/fit/confidence+reason/adjustments +
recommended_stay_tier + style_conflict; discover_circuits output ranked by
budget_compatibility (fits<stretch<premium<unknown, then cheapest); prompt gained the BUDGET
ADVISING state — and the exception is carved into READY alongside the season one (the lesson
from the seasonality prompt-conflict bug, applied preemptively). MONEY-IS-RANGES rule incl.
the flight-fare ban. Live verification (all pass): Munnar ₹22k → builds, "✅ Fits comfortably",
rounded range, "Confidence: High —" with reason; Dubai ₹20k Jan → advisory-only (range table,
4 levers, one question, NO plan); Udaipur luxury ₹30k → conflict advisory (palace-stay costs,
budget-up / boutique-instead / shorter — no silent downgrade). 60 offline tests, ruff+pyright
clean. Next: Phase B (preferences as constraints), Phase C (structured intake).

## 2026-06-06 04:50 — Phase B built & live-verified: preferences are now constraints
Two-layer pattern again (LLM judges phrasing, deterministic code applies): TripBrief gains
popularity_pref (iconic/balanced/offbeat) + avoid[] (hard filter) + must_include[] (beats every
bias incl. avoid); Attraction gains popularity 1-10 (None=unknown→neutral, NO personalization
theater — prompt forbids claiming hidden-gem curation when data is missing). Selector: ±0.8/pt
popularity bonus centred on 5 (quality floor: worth_visiting still dominates), avoid matched
on name+description, musts seeded first. Retrieval: extraction now returns 10-12 attractions
as a genuine icon+hidden-gem MIX with popularity scored; knowledge_cache rows versioned
internally (id@v2 — destination.id stays clean) so old icon-only cached destinations refetch.
LIVE-CAUGHT BUG #4: "no FORTS" (plural) didn't match "Amber Fort" (singular) — filter silently
missed, model patched around it in text and LEAKED VOICE ("the planner sneaked a couple of
forts in"). Fix: plural normalization in _matches_any (strip one trailing 's'; safe under
substring matching) + prompt insurance (never narrate corrections). Verified live: non-touristy
Paris leads with Coulée Verte/Buttes-Chaumont/covered passages, icons deprioritized (Eiffel
survives as ONE dusk photo stop for a photography couple — soft bias, not a ban, exactly as
designed); Jaipur "no forts" → zero forts, zero internals mentioned. 67 offline tests.
Remaining: Phase C (structured intake form).

## 2026-06-06 05:10 — Phases A+B DEPLOYED to production; main fast-forwarded
railway up → clean boot. Prod smoke (live SSE, Munnar ₹22k + hidden-gems ask): rounded range
₹13,500–18,500, ✅ Fits-comfortably verdict table, "Confidence: High —" with the knowledge-state
reason, transport as a labelled range only, and the plan visibly leaning local. Both
constraint phases live in one coherent release. main fast-forwarded 59adcec→7fd1ab5 and pushed
(user-authorized; covers seasonality + Phase A + Phase B). Prod = build/tripos-v1 = main.
Next: Phase C — compact structured intake (HTMX form composing the first chat message).

## 2026-06-06 05:30 — Scenario validation codified as a permanent, project-wide release gate
User elevated the lesson of this cycle into engineering policy: testing = three layers
(unit: does the code work / integration: do the modules compose / scenario validation: would a
REAL TRAVELER consider this correct and useful). Layer 3 is a MANDATORY release gate, not QA —
the 4 live-caught bugs (dropped enrichment slice; READY-vs-advisory prompt conflict; flight
fares from model memory; "no forts" plural miss) were all traveler-experience failures
invisible to 60+ green tests. Codified in THREE places, each chosen deliberately:
docs/policy.md (permanent section, fenced as ENGINEERING principle so it never enters the
system prompt — policy.md is otherwise the agent rulebook), CLAUDE.md Definition of Done (a
new mandatory checkbox: run the relevant scenarios LIVE for any behavior change; scenarios
BEFORE implementation for new features), and docs/scenarios.md preamble (formally the Layer-3
registry). Bar for personalization features: output must VISIBLY differ from the
unpersonalized output or the feature failed. Core principle: the advice the traveler receives
IS the product.

## 2026-06-06 06:00 — Phase C (structured intake) SHELVED: current conversational UX wins
Explored intake strategies for Phase C before building (form / in-flow chips / rich first
message / plan-first-ask-later / traveler memory, incl. a 2026-Gen-Z behavioral lens whose
"perfect" loop = instant draft + tappable assumption chips + shareable output — but that
requires two-stage sketch→verified planning to beat the 30-60s build latency, and depends on
an ICP we haven't confirmed). USER DECISION: the current UX is better — keep pure chat.
Rationale that holds: friction is already engineered down to ~one bullet-list round-trip;
the advisory moments (season/budget/luxury) ARE the product and only work as conversation;
one coherent interaction model beats bolted-on surfaces; and we're pre-data. Nothing of
Phase C reached docs or code, so nothing to unwind. REOPEN TRIGGER: real-user evidence —
mine tripos_trips transcripts (round-trips per plan, stall/abandon points) if friction
complaints become concrete. Next queued feature: Trip Comparison (its own stage 3-4 pass).

## 2026-06-06 09:00 — V2 Intelligence Upgrade: intent-first orchestration, NO pre-classifier
Diagnosed why "Suggest homestays in Didupe under ₹10,000" triggers itinerary questions: not a
routing-intelligence failure but a toolset + prompt-structure one. The system prompt's
GATHERING/READY slot machine is GLOBAL (it even forbids recommending stays before all trip
slots are known) and every tool is plan-shaped — the LLM has nothing to route a stays request
to. DECISION: keep the single agent as the router; no separate intent-classifier LLM call
(would add latency, cost, and a second source of truth — the agent already routes by tool
choice). Fix = (1) intent-scoped tools find_stays / find_restaurants / suggest_destinations,
(2) prompt restructured intent-first with the slot machine nested under PLAN_TRIP only
(advisory text kept VERBATIM — the READY-vs-advisory conflict bug lived exactly there),
(3) a dynamic instruction injecting today's date (the agent currently has ZERO date awareness,
so "I'm leaving today" can't resolve). Load-bearing reuse: trip_intelligence.enrich() already
retrieves stays/restaurants from one cached web fetch and runs from just a place name
(_stub_for); its cache key (slug:v2) is the SAME one build_trip uses — so find_stays("Didupe")
makes a later Didupe trip plan a cache HIT, not extra cost. Scenarios written first
(scenarios.md "Intent-driven service" section) per the Layer-3 gate; also retired the stale
"Paris is out of scope" scenario that contradicted worldwide retrieval.

## 2026-06-06 10:30 — V2 built: intent tools + travel context + package split (phases 1-3)
Shipped the redesign in one pass: (1) tripos_planner.py (750 lines, over the 500 cap) split
into a package — prompt / tools / recommend / compact / agent / streaming — with the public
import surface re-exported unchanged (locked by a test); (2) travel_context_now() registered
via @instructions, NOT system_prompt: instructions are re-evaluated every run and never
replayed from history, exactly right for "what is today". The date hint deliberately says
nothing about suitability — season verdicts stay with check_travel_season; (3) find_stays /
find_restaurants reuse trip_intelligence.enrich_by_name (new tiny public wrapper over the
_stub_for path) so they share the build's cache key; a FOCUSED fallback retrieval fires only
when the generic enrichment is thin for a specific ask (e.g. "homestays" in a village),
cached under its own {slug}:stays:{kind}:v1 key so it can never clobber the canonical :v2 row;
(4) suggest_destinations mirrors the circuits provider pattern (research + extraction, cached
per constraint-key) and reuses rank_circuits_by_budget — DestinationIdea duck-types on
est_per_person_budget, so destination ideas rank best-budget-fit-first with zero new ranking
code; (5) the dead-end guard's force nudge is now intent-aware (it names find_stays /
find_restaurants alongside build_trip) so a stalled homestay promise can't force an unwanted
trip build; per-tool streaming statuses for the same honesty reason.
OFFLINE TEST CAUGHT A REAL BUG before it shipped: the veg-preference filter matched "veg" as a
substring of "non-veg" — a steakhouse ranked as vegetarian-friendly. Same trap family as the
"no forts"/"Amber Fort" plural bug, inverted. Fixed by stripping negations before matching
(_veg_friendly). The test-first habit on pure ranking helpers paid for itself immediately.

## 2026-06-06 11:30 — V2 Layer-3 live validation PASSED (all 7 scenarios)
Ran the release gate via scripts/validate_v2.py (drives stream_reply — the exact web pipeline).
Intent scenarios: Didupe homestays (ranked pick+3 alts, prices/why/tradeoffs, honest about the
small village, ZERO itinerary questions); Kochi seafood (occasion handled with judgment — a
"best food" pick vs a "most romantic" pick; showed 2 strong options rather than padding);
December discovery (4-5 ideas, best-budget-fit first, tradeoffs, offer-to-plan); "leaving
today for Kerala" (resolved to June automatically — never asked WHEN; one consolidated
bullet round for group/budget/interests). Regression sweep UNCHANGED: Dubai-July advisory-only
then indoor-leaning plan on "continue with July" (ranges, confidence-with-reason, ✅ verdict);
non-touristy Paris leads hidden gems with Eiffel as one dusk photo stop (the designed soft
bias) + full budget contract; Goa luxury ₹30k → conflict advisory with levers, no silent
downgrade. Verdict: the intent-first restructure changed non-planning conversations without
regressing the planning ones — the nesting-not-rewording approach to the advisory text worked.
Kept scripts/validate_v2.py as the reusable Layer-3 driver.

## 2026-06-06 12:00 — V2 Intelligence Upgrade DEPLOYED to production (user-authorized)
Pushed build/tripos-v1 (a434ead) to GitHub and deployed the working tree to the prod Railway
service (railway up --service tripos-web). Boot clean; prod smoke verified the new build live:
"Best seafood restaurants in Kochi" through the real /chat/stream returned the V2 status
("Finding great places to eat…" — a string that only exists in this build) and streamed
recommendations directly, zero slot-gathering. The intent-first consultant is live.
main not yet fast-forwarded — awaiting explicit go-ahead, per convention.

## 2026-06-06 13:30 — UX & performance upgrade built: prewarm + live checklist + voice
Three mechanisms, all preserving quality (verified: the July Dubai plan's estimate range is
byte-identical pre/post — ₹47,000–₹68,000): (1) REAL SPEED — check_travel_season now
fire-and-forgets a background destination resolve (its season fetch already warmed enrichment),
so the conversation's dead time warms BOTH caches before the build turn; prerequisite was
in-flight coalescing (one task per place in web_intelligence.gather +
destination_intelligence.resolve) so an overlapping prewarm and build never double-pay.
Deliberately did NOT split the combined enrichment fetch into 4 parallel calls — 4x research
cost, and extraction (not research) dominates. (2) PERCEIVED SPEED — progress.py Reporter
(ContextVar, inherited by tool tasks, no-op when inactive) + stream_reply now RACES the run
iterator's anext() (where tool execution blocks — verified in pydantic-ai source) against the
progress queue, so ✓-checklist statuses stream mid-tool. Domain modules stay agent-agnostic via
optional on_progress/on_leg_done callbacks. Honesty contract: ✓ only on completed work (a
failed resolve never ticks). Live-verified: Dubai build streams the full cascade; Didupe shows
"Digging deeper for homestay options" exactly when the fallback fires. (3) VOICE — user chose
the browser Web Speech API over server-side Whisper (free, frontend-only, live interim text;
tradeoff: no Firefox, engine-dependent quality — mitigated by the smart-notepad design where
the user always edits before sending). Append-mode joining ("Plan a Japan trip." + "Eight
days."), readOnly input while recording, handlers detached on stop so stale speech can't land
in a cleared box, never auto-sends. Browser voice checks are manual (Web Speech can't be
driven by pytest) — listed in scenarios.md. Prewarm's live timing benefit on a truly cold
destination not yet measured (mechanism unit-tested; cache-hit fast path already proven) —
worth a timed check next time a new destination comes up naturally.

## 2026-06-06 14:00 — UX/perf upgrade DEPLOYED to production (user-authorized)
Pushed build/tripos-v1 (3d6601a) and deployed via railway up. Boot clean; prod smoke verified
the new build on the real /chat/stream: the Didupe homestays ask streamed the full live
checklist ("✓ Scanning stays in Didupe → ✓ Digging deeper for homestay options → ✓ Ranking
what fits your ask") — status events that only exist in this release. Prewarm + coalescing are
live on the same paths. Voice mic ships in this build; the manual browser voice checks
(scenarios.md) can now be done against prod directly. main not yet fast-forwarded.
