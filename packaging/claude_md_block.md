<!-- PACKAGING STUDIO: CONTEXT (managed) — do not edit by hand between these markers.
     Packaging Studio writes and refreshes this block during onboarding so every future
     session loads the project's design context instantly. Edit outside the markers freely;
     the studio only ever rewrites what's between them. -->
<!-- packaging-studio:begin -->

## Packaging Studio — Project Context

**Project:** TravelOS (TripOS v1)
**Description:** AI travel consultant that plans trips to any destination worldwide via a conversational planner agent (stays, restaurants, circuits, seasonality, feasibility, budgets). Working, deployed product — planning intelligence is the frozen baseline.
**Tech stack:** Python 3.12 · FastAPI 0.136 · Jinja2 server-rendered · HTMX 2 + Tailwind 4 + marked.js via CDN (no JS build step) · pydantic-ai/OpenRouter · Neon Postgres · PWA (manifest + sw.js) · deployed on Railway.
**Architecture:** chat page (landing) → POST /chat/stream (SSE: `t` deltas, `status`, `form`, `done`) → planner agent tools → markdown reply rendered by marked.js; trips persisted in trip_store (transcript + agent_messages); /trips, /trip/{id}, /trip/{id}/print, Google auth.
**UI vs. logic boundary:** Presentation (fair game): `src/agent/templates/*` (base, chat, _splash, _voice_input, login, trips, profile, welcome, print) + `src/agent/static/*`. Frozen: `agents/tripos_planner/*` (agent, prompt, tools, streaming, questionnaire), `tripos/*` modules, `tripos_web.py` routes/SSE contract, `web_auth.py`.
**Business domain:** Consumer travel planning (global destinations; India-first pricing in ₹).
**Audience / personas:** Travelers planning leisure trips — families, honeymooners, budget backpackers; mobile-heavy usage.
**Design goals:** Premium, immersive, travel-themed "living world." Feel: Apple/Linear/Airbnb-calibre polish — minimal, calm, cinematic, emotional. The itinerary must read like a crafted travel journal, never a chatbot wall of text. Full vision: `packaging/brain/project.md` + `packaging/ROADMAP.md`.
**Current UI maturity:** Basic — generic dark slate/sky chat-bubble UI, no design tokens, one splash animation, itineraries are long markdown walls, print view dumps the whole transcript, a11y/perf never audited.
**Conventions:** Templates in `src/agent/templates/`, static in `src/agent/static/`, tests in `scripts/tests/`, journal.md discipline, ruff+pyright+pytest clean, files ≤ ~500 lines, no JS build step (CDN only), docs stay in sync with code.

**Packaging Studio outputs live in** `packaging/` — Design Vision Documents, the `brain/` memory,
and `FRAMEWORK_IMPROVEMENTS.md`. Business logic is **frozen**; the studio changes presentation only.

<!-- packaging-studio:end -->
