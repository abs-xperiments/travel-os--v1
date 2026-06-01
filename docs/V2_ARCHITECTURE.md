# TripOS V2 Architecture — Provider-Agnostic Retrieval

*Lead architect synthesis. Audience: founder + AI engineer. Status: design for incremental rollout.*

---

## 1. Executive Summary

**What changes, in plain words:** Today TripOS can only plan trips to 24 hardcoded Indian destinations because every fact flows from static JSON files (`destination_catalog`). We are replacing the *data source*, not the *planning brain*. The deterministic engines that make TripOS good (feasibility math, attraction scoring, day-packing, budgeting) stay almost exactly as they are. We slot a **retrieval layer** underneath them so they can be fed data about *any* destination on Earth.

**Core principle:** Retrieval lives behind clean **interfaces**. The planner asks "give me destination knowledge for X" and gets back a standardized, typed object. It never knows or cares whether that object came from our curated catalog, a Wikivoyage page, a Perplexity web search, or (someday) Google Places. This is the single most important design goal.

```
        BEFORE                              AFTER
   planner ── imports ──► catalog     planner ──► DestinationProvider (interface)
   (24 India JSON files)                              │
                                          registry picks best adapter
                                          ┌──────┬──────┬──────────┐
                                       catalog  wikivoyage  perplexity ... (future: Google/Booking)
```

**Three moves:**
1. **Interfaces + registry** — five provider contracts returning our own types; a swappable registry.
2. **Inject, don't import** — `trip_planner` receives resolved data instead of fetching it; the catalog becomes the *fastest adapter*, not a dependency.
3. **Cache once** — one Neon table caches all retrieved knowledge with TTL, so we don't pay for web calls every chat turn.

**What V1 is and isn't:** V1 produces **web-grounded recommendations with reasoning and citations** — not live inventory, not bookings. Every price and rating is labeled an **estimate**. We never say "destination not supported"; on thin data we proceed with honest caveats.

---

## 2. What We PRESERVE (and Why)

These are working, load-bearing, and must survive untouched (or near-untouched):

| Kept | Why it stays |
|---|---|
| **SSE streaming** (`stream_reply` / `agent.iter()`) | Deliberately uses `agent.iter()` (not `run_stream()`) to stream text across tool-call boundaries. `run_stream()` would silently drop post-tool prose. Load-bearing. |
| **Dual persistence** (`trip_store`: `transcript` + `agent_messages`) | Display history vs. pydantic-ai continuation history are correctly separated. |
| **PDF print** (`GET /trip/{id}/print` → `print.html` → `window.print()`) | Zero-dependency. No server-side PDF lib. Keep it. |
| **Password gate middleware** | `secrets.compare_digest` constant-time compare. Fine as-is. |
| **`destination_catalog` + its 24 JSON files + `@lru_cache`** | Becomes the **fast-path adapter** (zero cost, zero latency). Not deleted. |
| **The 5 deterministic engines** | `check_feasibility`, `estimate_budget`, `select_attractions`, `build_itinerary`, `plan_trip` — pure, tested, correct. Reused by feeding them retrieved data. |
| **`services/llm.py` (`research()`, `build_model()`)** | Adapters call these; no changes to the service. |
| **`services/db.py` (asyncpg pool, `apply_migrations`)** | Cache layer reuses it; `statement_cache_size=0` Neon compatibility preserved. |

**The only code changes to existing engines:**
- `attraction_selector` — one-line signature change (accept `list[Attraction]` instead of `Destination`).
- `trip_planner` — remove the inline catalog import; accept injected destination knowledge.

Everything else in the planning core is unchanged.

---

## 3. The Provider-Agnostic Retrieval Layer (the heart)

The retrieval layer sits between **the world** (catalog, web, free APIs, future premium APIs) and **every planning engine**. The planner consumes *only* standardized types defined here.

### 3.1 The Five Provider Interfaces

Defined as Python `Protocol` classes (structural typing — lightweight, beginner-friendly, no inheritance ceremony). All return **our own typed result objects**, never raw dicts or provider-specific shapes.

```python
class DestinationProvider(Protocol):
    async def search(query: str, brief: TripBrief | None = None) -> list[DestinationSummary]
    async def get_knowledge(destination_id: str) -> DestinationKnowledge | None

class AccommodationProvider(Protocol):
    async def search(destination_id: str, base: str, nights: int,
                     group: GroupType, budget_per_night: float | None) -> list[Accommodation]

class RestaurantProvider(Protocol):
    async def search(destination_id: str, base: str,
                     food_pref: FoodPref, days: int) -> list[Restaurant]

class WeatherProvider(Protocol):
    async def get_forecast(lat: float, lon: float,
                           date_from: date, date_to: date) -> WeatherForecast
    async def get_seasonal_norms(destination_id: str, month: int) -> SeasonalNorms

class GeocodingProvider(Protocol):
    async def geocode(place_name: str) -> Coordinates | None
```

### 3.2 The Registry (the swap point)

A ~40-line module-level singleton. Adapters register by **role** + **priority** at app startup. Callers ask for a role and get the highest-priority available adapter — never a concrete class.

```python
class ProviderRegistry:
    def register(role: str, provider: Any, priority: int = 0) -> None
    def get(role: str) -> Any            # highest-priority available adapter
    def get_all(role: str) -> list[Any]  # ordered, for fallback chains
```

Roles: `destination`, `accommodation`, `restaurant`, `weather`, `geocoding`.

**This is the seam.** Adding Google Places later = one `register()` line in startup + one new adapter file. **Zero planner changes.**

### 3.3 NOW Adapters vs FUTURE Adapters

| Role | NOW (Phase 1–2, free/open) | FUTURE (Phase 3, premium — slot in, no planner change) |
|---|---|---|
| Destination | **CatalogAdapter** (priority 10, fast path), **PerplexityAdapter** (priority 1, fallback via `research()`), **WikivoyageAdapter** | Google Places, TripAdvisor |
| Accommodation | **PerplexityAccommodationAdapter** (`is_live_inventory=False`, prices = estimates) | Booking.com, Expedia, Airbnb (`is_live_inventory=True`) |
| Restaurant | **PerplexityRestaurantAdapter** | Google Places, TripAdvisor, Zomato, Viator/GetYourGuide |
| Weather | **OpenMeteoAdapter** (free, no key, 16-day forecast + climate norms) | OpenWeatherMap, Tomorrow.io |
| Geocoding | **NominatimAdapter** (OSM, free, 1 req/s, cached 30d+) | Google Geocoding, HERE |

**Startup registration (the only place concrete adapters appear outside `adapters/`):**
```python
registry.register("destination",   CatalogDestinationAdapter(),   priority=10)
registry.register("destination",   WikivoyageAdapter(),           priority=5)
registry.register("destination",   PerplexityDestinationAdapter(),priority=1)
registry.register("accommodation", PerplexityAccommodationAdapter())
registry.register("restaurant",    PerplexityRestaurantAdapter())
registry.register("weather",       OpenMeteoAdapter())
registry.register("geocoding",     NominatimAdapter())
# FUTURE: registry.register("accommodation", BookingComAdapter(), priority=20)
```

### 3.4 The Verification Step (trust, but verify)

Before thin retrieved data is cached and served, a `verifier` cross-checks it. **It never blocks a plan** — it degrades gracefully to honest caveats.

```python
def verify(candidate: DestinationKnowledge, geocoder: GeocodingProvider) -> VerificationResult
# VerificationResult(confirmed: bool, confidence: float, lat, lon,
#                    canonical_name, notes: list[str], sources_checked: list[str])
```

Logic:
- **Geocode check** (Nominatim) + **existence check** (Wikipedia/Wikivoyage) → confidence score.
- `confirmed=True` even at low confidence (0.3–0.69); `notes` surface as caveats to the user.
- `confirmed=False` only when geocode fails AND no encyclopedia article AND the name looks hallucinated.
- Plausibility: ≥1 attraction present, durations in 0.5–8h range, coords valid.

**The resolution chain** (single source of truth — defined once, used everywhere):
```
1. CatalogAdapter.get_knowledge(id)     # in-memory, 0ms, 0 cost  → HIT? done.
2. cache.get(key)                        # Neon, ~5ms              → fresh HIT? done.
3. PerplexityAdapter.get_knowledge(id)   # research(), 3–8s, ~$0.001
4. verifier.verify(candidate)            # geocode + existence
5. cache.set(key, result, ttl)           # persist for next time
```

---

## 4. Revised Architecture by Layer

| Module | Responsibility (one line) | Status |
|---|---|---|
| **Layer 0: Contracts** | | |
| `provider_interfaces/` | The 5 Protocols + all standardized result types. The only types planners see. | **new** |
| `provider_registry/` | Role→adapter map by priority; the swap seam. | **new** |
| **Layer 1: Adapters** | | |
| `providers/catalog_adapter` | Wraps existing catalog as `DestinationProvider` (fast path). | **new** |
| `providers/perplexity_adapter` | Destination/Accommodation/Restaurant via `research()` + structured extraction. | **new** |
| `providers/wikivoyage_adapter` | Free destination summaries via Wikivoyage REST. | **new** |
| `providers/openmeteo_adapter` | Forecast + climate norms (free, no key). | **new** |
| `providers/nominatim_adapter` | Geocoding (free, rate-limited, heavily cached). | **new** |
| **Layer 2: Shared services** | | |
| `knowledge_cache/` | One Neon-backed cache for all providers; TTL/freshness; `get`/`set`. | **new** |
| `verifier/` | Cross-source confidence check; never blocks, emits caveats. | **new** |
| `stay_restaurant_ranker/` | **All** stay+restaurant ranking/justification logic, once. Pure. | **new (P2)** |
| **Layer 3: Composers** | | |
| `stay_planner/` | Stay-first: anchor attractions to accommodation zones, allocate nights. | **new (P2)** |
| `circuit_discovery/` | "N days, where?" → propose/rank 2–4 stop circuits. | **new (P3)** |
| `circuit_distance_estimator/` | Pure haversine + terrain → travel hours between legs. | **new (P3)** |
| **Layer 4: Existing engines** | | |
| `attraction_selector` | Score + feasibility-gate attractions. | **extend** (1-line sig) |
| `trip_planner` | Compose a plan from injected knowledge. | **refactor** (drop catalog import) |
| `itinerary_builder`, `budget_estimator`, `trip_feasibility_checker` | Day-pack, total, feasibility math. | **unchanged** |
| `destination_catalog` | The 24 JSON files; now wrapped by CatalogAdapter. | **unchanged** |
| **Layer 5: Surface** | | |
| `agents/tripos_planner.py` | Tools call registry, not catalog; new `discover_circuits` tool. SSE untouched. | **extend** |
| `tripos_web.py` | Register adapters in lifespan. Routes/SSE/PDF/auth untouched. | **extend** (minimal) |
| `trip_store` | + migration `002_knowledge_cache.sql`. Existing code unchanged. | **extend** (migration only) |

---

## 5. Shared Data Models

All in `provider_interfaces/`, extending `tripos/models.py` conventions (Pydantic, StrEnum). Existing `Destination`/`Attraction` stay in `models.py` unchanged for the catalog and tests.

**`DestinationKnowledge`** — the canonical type every `DestinationProvider` returns.
```
id, name, country, region | description | lat, lon
bases: list[str]                      # towns to stay in
good_for: list[TravelStyle]
attractions: list[Attraction]         # may be empty (thin data)
nearest_railhead, nearest_airport | best_months: list[int]
climate_notes: str
data_source: str                      # 'catalog' | 'perplexity' | 'wikivoyage'
citation_urls: list[str]
verification_confidence: float        # <0.7 → show as caveat
caveats: list[str]
cached_at: datetime | None, ttl_hours: int
```
> Wraps existing `Destination` + `Attraction` so engines consume it unchanged. CatalogAdapter maps JSON 1:1; web adapters synthesize it.

**`DestinationSummary`** — lightweight discovery card: `id, name, country, region, tagline, good_for, fit_score, data_source`.

**`Accommodation`**
```
id, name, destination_id, base | accommodation_type (hotel/homestay/resort/guesthouse/hostel)
price_per_night_low/high, currency='INR' | rating_estimate, review_count_estimate
amenities, group_suitability, highlights
is_estimate=True | is_live_inventory=False   # ← the V1↔future-booking seam
source_urls, disclaimer='Estimate only — verify before booking.'
```

**`Restaurant`**
```
id, name, destination_id, base | cuisine, price_tier (budget/mid/upscale)
food_prefs_ok: list[FoodPref]                # hard-filtered for veg/jain/vegan
rating_estimate | is_estimate=True | source_urls
disclaimer='Verify hours and menu before visiting.'
```

**`WeatherForecast`** — `destination_id, date_from/to, daily_summaries: list[DailyWeather], overall_advice, is_live: bool, source ('open-meteo'|'seasonal_norms'), caveats`.
`DailyWeather`: `date, temp_max_c, temp_min_c, precip_mm, summary`.

**`StayPlan` / `StayLeg`** (Phase 2) — stay-first structure.
```
StayLeg:  destination_id, leg_index, stay_area, recommended_stay,
          check_in_day, check_out_day, nights, attractions, itinerary, feasibility
StayPlan: legs: list[StayLeg], total_nights,
          booking_note='Recommendations only — not booked. Prices are web-sourced estimates.'
```

**`CircuitProposal` / `RankedCircuit`** (Phase 3).
```
CircuitProposal: circuit_id, name, legs: list[CircuitLeg], total_days,
                 transits: list[LegTransit], budget_estimate, style_tags, region
RankedCircuit:   proposal, score, why: list[str], rank
```

**`Coordinates`** — `lat, lon` (+ `canonical_name`, `country_code` from Nominatim).

**Evolved `TripPlan`** — all new fields optional with defaults so existing persisted trips and the print template keep working:
```
# preserved: brief, destination_id, attractions, itinerary, budget, feasibility
stays: StayPlan | None = None              # P2
accommodations: list[Accommodation] = []   # P2
restaurants: list[Restaurant] = []         # P2
weather: WeatherForecast | None = None     # P2
knowledge_sources: list[str] = []
data_caveats: list[str] = []
```

**Cache row** (`tripos_knowledge_cache`, internal — not a public model):
```
cache_key text PK   # '{role}:{normalized_query}' e.g. 'destination:munnar', 'geocoding:munnar+kerala'
kind text           # 'destination'|'accommodation'|'restaurant'|'weather'|'geocode'
data jsonb          # model_dump_json() of the cached object
fetched_at timestamptz, ttl_hours int
```

---

## 6. New End-to-End Data Flow

The web layer, SSE, and persistence are **identical** to today. The change is *inside* the agent's tools.

### Path A — "I know where I'm going" (single destination)

```
Browser POST /chat/stream (unchanged)
 → trip_store.ensure_trip / load_agent_messages          [unchanged]
 → stream_reply(message, history)  via agent.iter()       [unchanged streaming]
     → LLM may stream "Let me look up Kyoto for you…"     [status while tool awaits]
     → tool: build_trip(destination_id, brief)
         → resolve_destination(id):
              catalog HIT? ──► DestinationKnowledge (0ms)
              else cache HIT? ──► DestinationKnowledge (~5ms)
              else research() ──► extract ──► verify ──► cache.set  (3–8s, once/TTL)
         → trip_planner.plan_trip(brief, knowledge)        [refactored: injected]
              → attraction_selector(knowledge.attractions, brief)   [1-line change]
              → itinerary_builder(...)                      [unchanged]
              → budget_estimator(...)                       [unchanged]
              → check_feasibility(...)                      [unchanged]
         → _compact_plan(plan) dict  (+ caveats, citations)
     → LLM streams prose plan, citing sources, labeling estimates
 → SSE deltas → browser (marked.parse)                     [unchanged]
 → trip_store.append_turn                                  [unchanged]
GET /trip/{id}/print → PDF                                 [unchanged]
```

### Path B — "I have N days, where should I go?" (circuit discovery, Phase 3)

```
 → tool: discover_circuits(start_city, days, budget, interests, region)
     → registry.get("destination").search(...)   # catalog first; web if <6 hits
     → geocode candidates (Nominatim, cached)
     → generate 2–4 stop circuits (prune: legs <300km, stops ≤ days//2)
     → per candidate: night_allocator (density-weighted, never equal splits)
                      circuit_distance_estimator (travel hours)
                      budget_estimator (rough total)        [unchanged]
     → circuit_ranker → top 3 RankedCircuit  (+ plain-English "why")
     → cache ranked list 24h
 → LLM streams "Here are 3 circuits…" → user picks one
 → user picks → build_trip per leg  (= Path A, repeated)
```
> Phase 1/2 returns **previews only** (top-3 attraction names + nights per stop) to keep tool responses < 1000 tokens. Full per-leg itineraries are built only after the user selects a circuit.

---

## 7. Caching, Cost & Latency Strategy

**Cache-first is the primary cost control.** Every adapter checks `knowledge_cache` before any network call. On a hit, marginal cost ≈ one `asyncpg` fetchrow (sub-millisecond, free).

**One shared Neon table** (migration `002`):
```sql
CREATE TABLE tripos_knowledge_cache (
  cache_key  text PRIMARY KEY,         -- '{role}:{normalized_query}'
  kind       text NOT NULL,
  data       jsonb NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  ttl_hours  int NOT NULL DEFAULT 168
);
CREATE INDEX ix_kc_kind ON tripos_knowledge_cache (kind);
-- freshness: WHERE fetched_at > now() - (ttl_hours || ' hours')::interval
```

**TTL by volatility:**

| Data | TTL | Why |
|---|---|---|
| Destination knowledge | 168h (7d) | Attractions/descriptions change rarely |
| Geocode coordinates | 720h (30d) | Coordinates never change |
| Accommodation | 24h | Prices fluctuate |
| Restaurant | 72h | Menus/closures change |
| Weather forecast | 6h | Changes hourly; **not** cached if live |
| Climate norms | 90d | Static |

**Rough cost (Perplexity Sonar ≈ $1/1M tokens; extraction via `build_model('fast')` ≈ negligible):**
- Destination knowledge query: ~$0.001 per fetch, **once per week per destination**.
- New destination first-visit (knowledge + stays): **< $0.01 total**, then ~$0 from cache.
- 100 unique destination lookups/week: **< $0.25/week**.
- Open-Meteo, Nominatim, Wikivoyage: **free**.

**Latency:** catalog hit 0ms · cache hit ~5ms · cache miss (Perplexity) 3–9s **once per TTL window**. SSE streams a "Researching…" preamble so the UI stays responsive during the miss.

**Mitigations:**
- Concurrent independent calls via `asyncio.gather()` (e.g. stays + restaurants).
- Nominatim 1 req/s guarded by `asyncio.Semaphore(1)` + 30d cache → rarely hit.
- Neon down → `cache.get` returns `None` (miss), `cache.set` swallows + logs → degrades to always-live, never crashes.
- Negative-cache thin results (7d TTL) so obscure destinations aren't re-fetched every turn.

---

## 8. Proposed Folder / Module Map

Beginner-friendly: each folder = one responsibility + a plain-English `README.md`; files < ~300 lines.

```
src/agent/
├─ tripos/
│  ├─ models.py                      # unchanged + new shared types
│  ├─ provider_interfaces/
│  │  ├─ __init__.py                 # the 5 Protocols + result types  ← import ONLY from here
│  │  └─ README.md
│  ├─ provider_registry/
│  │  ├─ __init__.py                 # ~40-line registry singleton
│  │  └─ README.md
│  ├─ providers/                     # concrete adapters (imported only at startup)
│  │  ├─ catalog_adapter/
│  │  ├─ perplexity_adapter/
│  │  ├─ wikivoyage_adapter/
│  │  ├─ openmeteo_adapter/
│  │  ├─ nominatim_adapter/
│  │  └─ README.md
│  ├─ knowledge_cache/
│  │  ├─ __init__.py
│  │  ├─ migrations/002_knowledge_cache.sql
│  │  └─ README.md
│  ├─ verifier/
│  ├─ stay_restaurant_ranker/        # P2: ALL stay+restaurant ranking, once
│  ├─ stay_planner/                  # P2
│  ├─ circuit_discovery/             # P3
│  ├─ circuit_distance_estimator/    # P3
│  ├─ destination_catalog/           # UNCHANGED (24 JSON files + lru_cache)
│  ├─ attraction_selector/           # 1-line signature change
│  ├─ trip_planner/                  # refactored (injected knowledge)
│  ├─ itinerary_builder/             # unchanged
│  ├─ budget_estimator/              # unchanged
│  ├─ trip_feasibility_checker/      # unchanged
│  └─ trip_store/                    # unchanged code; new migration
├─ agents/tripos_planner.py          # tools → registry; new discover_circuits
├─ services/{llm.py, db.py}          # unchanged
└─ tripos_web.py                     # lifespan registers adapters; routes unchanged
```

---

## 9. Conflicts & Duplication Found — and How Resolved

The six section designs overlapped heavily. Reconciled decisions:

| Conflict | Resolution |
|---|---|
| **Module naming** — `retrieval/`, `destination_intelligence/`, `provider_interfaces/`, scattered top-level adapters. | **One** `provider_interfaces/` (contracts) + `provider_registry/` + `providers/` (adapters). Single convention. |
| **Data model duplication** — `DestinationKnowledge` defined 5× with differing fields; `StayOption`/`StayRecommendation`/`Accommodation`; `WeatherForecast` twice; `Coords`/`Coordinates`/`GeoPoint`. | **One reconciled set** (§5). One `DestinationKnowledge`, one `Accommodation`, one `Restaurant`, one `Coordinates`, one `WeatherForecast`. |
| **Ranking logic** — appeared in `circuit_ranker`, `stay_restaurant_ranker`, and inline. | Defined **once**: attractions stay in `attraction_selector`; stays+restaurants in `stay_restaurant_ranker`; circuits in `circuit_discovery`. Shared `_review_quality_score` lives in the ranker. |
| **Cache** — separate per-provider tables vs. one shared table; multiple migration files all numbered `002`. | **One** `tripos_knowledge_cache` table, `kind` discriminator, one migration `002_knowledge_cache.sql`. Geocode stored in same table with long TTL. |
| **`attraction_selector` change** — "replace signature" vs. "add overload keeping old." | **Replace** signature to `list[Attraction]` (only caller is `trip_planner`); update its tests in the same PR. Cleaner, no dead path. |
| **Where resolution chain lives** — duplicated in agent vs. `destination_intelligence`. | **One** `resolve_destination()` helper (catalog→cache→retrieve→verify→cache), called by the `build_trip` tool. |
| **Stay/restaurant scope** — Phase 1 vs Phase 2. | Deferred to **Phase 2**. Phase 1 keeps flat-rate budget placeholders to ship the global-coverage win first. |
| **Circuit discovery** — claimed "Phase 1 core" by one section. | Deferred to **Phase 3**. It's the largest new surface and not needed for the first end-to-end win. |

---

## 10. Phased, Incremental Roadmap

Each phase is independently shippable and keeps streaming/web/persistence/PDF working.

### Phase 1 — Global single-destination via retrieval (BUILD THIS FIRST)
**Smallest end-to-end win:** plan a trip to *any* destination worldwide, behind the provider interface, with caching. App still streams.

Ships:
- `provider_interfaces/` (`DestinationProvider`, `GeocodingProvider` + types)
- `provider_registry/`
- `knowledge_cache/` + migration `002`
- `providers/`: CatalogAdapter, PerplexityDestinationAdapter, NominatimAdapter (+ Wikivoyage optional)
- `verifier/`
- Refactor: `trip_planner.plan_trip(brief, knowledge)`; `attraction_selector(attractions, brief)`
- Agent: `build_plan`→`build_trip` (async tool); `list_destinations`→registry; system prompt drops "India only"
- Startup: register adapters in lifespan

**Size:** medium. ~8 new small modules + 2 one-line engine edits + 1 migration.
**Highest-risk item, test FIRST:** the **async tool boundary** — switching `build_plan` from `tool_plain` (sync) to `agent.tool()` (async) so it can `await` the cache/adapter. Confirm `agent.iter()` SSE streaming still works locally before anything else.

### Phase 2 — Stay-first + intelligence (richer plans)
Ships:
- `providers/`: PerplexityAccommodationAdapter, PerplexityRestaurantAdapter, OpenMeteoAdapter
- `stay_restaurant_ranker/`, `stay_planner/`
- Real budget: replace flat `_STAY_PER_NIGHT`/`_FOOD_PER_DAY` constants with retrieved estimates; add `currency` to budget types
- Evolved `TripPlan` (stays/accommodations/restaurants/weather optional fields)
- `_compact_plan` + print template gain optional "Where You Sleep" / weather sections

**Size:** medium–large.

### Phase 3 — Circuits + premium adapters
Ships:
- `circuit_discovery/`, `circuit_distance_estimator/`, night allocation, `discover_circuits` tool
- Premium adapters (Google Places, Booking.com, Expedia, TripAdvisor, Viator, GetYourGuide, Airbnb) — each is one new file + one `register()` line, **zero planner change**
- `is_live_inventory=True` path → UI upgrades labels from "estimate" to "live"

**Size:** large.

---

## 11. Risks & Limitations

- **Prose→typed extraction is fragile.** Perplexity returns prose; extraction can mis-parse `duration_hours`/`worth_visiting`. *Mitigation:* Pydantic validation + lenient defaults (e.g. `duration=2.0`, `worth_visiting=7`) + a `data_confidence` flag surfaced as caveats. Never crash the plan.
- **Thin data for obscure places.** *Mitigation:* allow empty `attractions`; proceed with ≥1 stop + honest caveats; never "not supported." Feasibility math already handles 1–2 attractions.
- **Async tool migration** (Phase 1's #1 risk). *Mitigation:* smoke-test SSE before building on it.
- **Cache staleness.** 7-day TTL can hide closures/price changes. *Mitigation:* show `cache_age_days` in caveats; offer a `force_refresh` option.
- **Nominatim rate/ToS.** *Mitigation:* required User-Agent header, `Semaphore(1)`, 30d cache → one geocode per place ever.
- **Currency.** Budget engine is INR-only. *Mitigation:* add `currency` field to budget types in Phase 2; until then label non-INR clearly.
- **Estimate accuracy.** All prices/ratings are web-grounded estimates, never live. The `is_estimate`/`is_live_inventory` flags + disclaimers are mandatory in the UI.
- **Beginner over-abstraction.** 5 interfaces + adapters is a lot. *Mitigation:* Protocols (not ABCs), tiny files, per-folder README, registry is the only "clever" piece.

---

## 12. Key Decisions for the Product Owner

Genuine forks — pick before/early in Phase 1:

1. **Rollout scope: worldwide vs. India-first?** The architecture supports global from Phase 1. India-first (catalog + nearby retrieval) lowers cost/QA risk and lets you tune extraction prompts on familiar ground. *Recommendation: ship Phase 1 worldwide but soft-launch with India-heavy prompts; the cache makes global cheap.*

2. **Acceptable per-trip retrieval spend?** ~$0.01 for a brand-new destination, ~$0 thereafter. Set a comfort ceiling (e.g. "< $0.05/new destination, < $X/week"). This decides whether to use Sonar Pro for thin data and how aggressive TTLs should be.

3. **Recommendations-only vs. begin booking groundwork?** V1 is recommendations only (`is_live_inventory=False`). The seam exists for live booking. Decide whether Phase 3 invests in real booking adapters (commercial deals, legal/payments) or stays recommendation-only indefinitely.

4. **Which premium providers to wire first (Phase 3)?** Options: Google Places (richest place data/reviews) vs. Booking.com/Expedia (accommodation breadth) vs. Viator/GetYourGuide (activities/affiliate revenue). *Affiliate links may be the fastest path to revenue without taking payments.*

5. **Structured plan storage?** Today plans live only in chat history (recoverable by re-running the agent). Adding a queryable `plan_jsonb` column enables analytics, "my trips" dashboards, and sharing — but is extra schema work. Defer to Phase 2/3?

6. **Extraction model trade-off.** `build_model('fast')` (cheap, occasionally inconsistent) vs. structured output directly on Sonar (may be unreliable) vs. a stricter mid-tier model. Affects both cost and data quality — pick before implementing the Perplexity adapter.

---

*Bottom line: we are swapping the data source, not rewriting the brain. Phase 1 — global single-destination behind the `DestinationProvider` interface with a shared cache, app still streaming — is the smallest change that proves the whole architecture. Build that first, test the async tool boundary before anything else.*