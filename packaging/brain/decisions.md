# Design Decisions — TravelOS (TripOS v1)

> Design decisions and the reasoning behind them, so future phases stay coherent and don't
> re-litigate settled questions. Newest at the bottom. Append at the end of each phase and
> whenever a real decision is made. Include decisions you **rejected** and why.

## 2026-07-15 — Onboarding — Stay on FastAPI/Jinja/HTMX; no React/Next.js rewrite
- **Chose:** keep the server-rendered stack and layer immersion via CDN libraries (Three.js,
  GSAP/Motion, Web Audio) — because the product works, the repo rule is "no JS build step,"
  and packaging never rebuilds (Principle #10).
- **Over:** Next.js/React Three Fiber rewrite (vision doc mentions R3F) — rejected: it would
  rewrite every working route/template, freeze-violating and high-risk. If a build step ever
  becomes necessary, it goes to the user as an explicit decision first.
- **Affects:** all tooling choices must run buildless via CDN/ESM.

## 2026-07-15 — Onboarding — Premium itinerary = frontend transform of agent markdown
- **Chose:** parse the finished markdown reply client-side into structured components (hero,
  day chapters, cards, budget summary) — because generation, prompts, and the SSE contract are
  frozen; the markdown structure (day headings, tables, lists) is stable enough to map.
- **Over:** adding structured-output markers/JSON to the agent — rejected without explicit
  permission (changes planner output = logic). May be proposed later as a suggestion.
- **Affects:** renderer must degrade gracefully to plain markdown when parsing doesn't match.

## 2026-07-15 — Phases 3–6 — "Golden Hour Atlas" design language
- **Chose:** warm night-ink OKLCH palette + gold/ember accents, Fraunces display serif +
  Inter UI, glass panels over a CSS living horizon keyed to the user's local hour
  (dawn/day/dusk/night) — psychology axis: arriving should feel like a place, not software.
- **Over:** light editorial theme (fought the existing night-train brand equity) and a WebGL
  world (perf risk, build-step pressure; CSS/SVG hits the bar for v1).
- **Affects:** all colors flow from theme.css tokens; no raw hex in templates.

## 2026-07-15 — Phase 4 — Brand stays "TripOS" in-app
- **Chose:** keep TripOS everywhere the traveler looks — the frozen agent greeting, prompts,
  splash and manifest all say TripOS; a split brand would feel broken.
- **Over:** renaming UI to TravelOS (would desync from frozen backend copy).
- **Affects:** "TravelOS" appears only in internal docs until a coordinated rename.

## 2026-07-15 — Phase 5 — Journal transform is clone-based with sacred fallback
- **Chose:** itinerary.js builds the journal from a CLONE of the rendered markdown and swaps
  only on full success; <2 day-markers or any exception leaves the original untouched.
- **Over:** in-place DOM restructuring (a mid-transform error could destroy content).
- **Affects:** any future renderer change must preserve the clone-then-swap contract.

## 2026-07-15 — Phase 6 — Final-PDF selection = "latest reply that transforms to a journal"
- **Chose:** print.html renders every assistant turn off-screen and keeps the LAST one that
  parses as a full itinerary — chat, iterations and prompts never print; honest fallback
  note when no finished itinerary exists.
- **Over:** printing the whole transcript (old behavior) or changing trip_store to mark a
  "final" itinerary (logic — forbidden; noted as v2 suggestion #1 in ROADMAP).
- **Affects:** PDF quality depends on the shared DAY_RE detection in itinerary.js.

## 2026-07-15 — Phase 6 — Service worker: stale-while-revalidate for /static/
- **Chose:** bump cache to tripos-v2 + background refresh, so deployed design assets can't
  go permanently stale (perceived-performance plumbing, no app behavior touched).
- **Over:** cache-first forever (would pin the old theme on installed PWAs).
