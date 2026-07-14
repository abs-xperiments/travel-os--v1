# Project Memory — TravelOS (TripOS v1)

> Durable project facts Packaging Studio relies on, beyond the `CLAUDE.md` snapshot. Read this
> first when re-activating on this project. Update when the product itself changes.

## What it does (frozen baseline)
AI travel consultant chatbot. Plans trips to any destination worldwide through a pydantic-ai
planner agent with real tools: suggest_destinations, discover_circuits, find_stays,
find_restaurants, check_travel_season, feasibility/budget engines. Streams replies over SSE as
markdown. Google sign-in, saved trips (Neon), print view, installable PWA, deployed on Railway.
This behavior — including every prompt, tool, and planning module — is preserved exactly.

## Stack & structure
- **Framework / build:** FastAPI + Jinja2 server-rendered; HTMX 2, Tailwind 4 (browser CDN),
  marked.js — all via CDN, **no JS build step** (repo rule). Python: uv/ruff/pyright/pytest.
- **Where UI lives (fair game):** `src/agent/templates/` — base.html, chat.html (431 lines:
  bubbles + SSE reader + questionnaire renderer + profile menu), _splash.html (train splash),
  _voice_input.html, login.html, trips.html, profile.html, welcome.html, print.html.
  `src/agent/static/` — manifest, sw.js, icons.
- **Where logic lives (frozen):** `src/agent/agents/tripos_planner/` (agent, prompt, tools,
  streaming, questionnaire spec, progress), `src/agent/tripos/` (18 atomic modules),
  `src/agent/tripos_web.py` (routes + SSE event contract), `src/agent/web_auth.py`.
- **Design system state:** none — raw Tailwind utility classes, hardcoded slate/sky palette,
  no tokens, no component layer, minimal `.md` CSS in base.html.

## The presentation seam (most important fact)
The agent's itinerary arrives as **markdown text** through SSE events:
`{"t": delta}` (text chunk), `{"status": …}` (tool progress), `{"form": spec}` (questionnaire),
`{"done": true}`. Rendered client-side by marked.js into one chat bubble. All premium itinerary
presentation must be built by transforming this markdown **after generation, in the frontend** —
never by changing prompts or planner output. `stream_reply` uses `agent.iter()` deliberately
(streams across tool boundaries) — do not touch.

## Screens & flows
- **/ (chat = landing):** greeting + example chips; browsable logged out; sending gated by auth
  (401 → sign-in bubble). States: fresh, streaming (typing cursor + progress notes), form,
  error, restored transcript.
- **/login:** Google-only sign-in.
- **/trips:** saved-trips list (owner-scoped).
- **/trip/{id}:** reopen a trip (404 if foreign).
- **/trip/{id}/print:** print-optimized page → window.print() = PDF. Currently dumps the FULL
  transcript including user turns.
- **Splash (_splash.html):** train + steam animation on load.

## Constraints & risks
- **No JS build step** — React/R3F/bundlers are off-limits unless the user explicitly approves
  introducing a build step. Three.js, GSAP, etc. are fine via CDN/ESM imports.
- **SSE contract is frozen** — the premium renderer must consume the existing event shapes.
- **print.html tangle:** "final itinerary only" PDF needs a way to pick the final itinerary out
  of the transcript. Doing it as frontend selection (last assistant message containing a
  day-by-day plan) is presentation; anything touching trip_store/agent is out of scope.
- **Tailwind browser CDN** is a prototyping build (repo acknowledges); production polish phase
  may propose precompiled CSS — surface as a decision, don't do silently.
- **India-first pricing (₹)** baked into questionnaire renderer formatting — keep.
- Perf-sensitive: chat streams re-parse the full accumulated markdown per delta (marked.parse
  on every chunk) — fine today, matters once the renderer gets heavier.

## Accessibility & performance baseline
- Never audited. Known gaps: no skip links/landmarks, contrast unverified, questionnaire chips
  are buttons (good) but focus states are default, no `prefers-reduced-motion` handling in
  splash, chat log has no aria-live, examples/menus keyboard-usable but untested.
- Perf: CDN Tailwind runtime compiler + marked re-parse per delta; no image weight yet; PWA
  shell is light. No CWV measurements exist.

## Product vision (the packaging north star)
World's first "AI Travel Operating System" — planning feels like the journey has already begun.
A living, breathing travel world: atmosphere, motion, light, sound; UI dissolves into the world.
Design language: minimal, premium, calm, cinematic, organic, timeless (Apple/Linear/Airbnb/
Stripe calibre — never "AI demo" aesthetics). AI feels invisible — a travel companion, not a
chatbot. Itinerary = interactive travel journal: each day a chapter, budgets as elegant visual
summaries, weather as atmosphere. Every interaction answers: "does this make the user feel more
like they are already traveling?" Full roadmap: `packaging/ROADMAP.md`.
