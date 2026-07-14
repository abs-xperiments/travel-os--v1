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
