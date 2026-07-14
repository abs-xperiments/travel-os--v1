# TravelOS — Master Packaging Roadmap

*Packaging Studio · created 2026-07-15 · status: Phases 1–8 delivered on `packaging/premium-experience` (Phase 8's live-audit half awaits your deploy — see packaging/SETUP-GUIDE.md). Deferred by decision: sound (needs sourced audio assets), WebGL world v2, OG share image.*

**Mission:** transform TripOS's working AI planner into the world's first travel-planning
experience that feels like the journey has already begun — premium, immersive, living —
**without changing one line of planning logic**. Business logic is frozen. Presentation only.

**The standard for every decision:** *"Does this make the user feel more like they are already
traveling?"* If ordinary vs. unforgettable, choose unforgettable — while staying minimal, calm,
fast, and accessible (Apple/Linear/Airbnb calibre, never "AI demo" aesthetics).

**Global constraints (apply to every phase):**
- Frozen: `agents/tripos_planner/*`, `tripos/*`, `tripos_web.py` routes + SSE contract, `web_auth.py`, prompts, tools, planning pipeline.
- No JS build step — all frontend libraries via CDN/ESM (Three.js, GSAP/Motion One, Web Audio). Introducing a build step requires explicit user approval first.
- Every phase: packaging branch → vertical slices → a11y + perf QA → journal.md entry → deploy → verify → commit → push → user review before next phase.
- `prefers-reduced-motion` honored everywhere; every animation must name its job.
- Accessibility floor: WCAG 2.2 AA. Perf budget: LCP < 2.5s on mid-range mobile, no jank (60fps or degrade gracefully).

---

## Phase 1 — Repository Audit & Technical Understanding ✅ DONE (2026-07-15)

Read-only analysis; context persisted to `CLAUDE.md` (studio block) + `packaging/brain/`.
Key finding: the presentation seam is the SSE→markdown→marked.js pipeline; all itinerary
presentation work happens after generation, in the frontend. Details: `packaging/brain/project.md`.

---

## Phase 2 — Product Vision, Research & Experience Strategy

**Goal:** convert the vision into a concrete, agreed experience strategy — so every later phase
executes instead of debates.
**Scope:** research + written deliverables only. Zero code.
**Features / deliverables:**
- Experience Strategy doc: emotional arc of a session (arrive → wonder → converse → plan → journal → export), the "living world" concept spec (day/night, weather moods, ambient layers), sound philosophy (opt-in, subtle, never autoplay-loud).
- Design research: award-winning travel/immersive sites, motion design references, travel psychology & emotional design principles — distilled into what TravelOS adopts/rejects.
- **Idea backlog: 100+ innovative ideas**, categorized (visual/motion/audio/personalization/AI interactions/gamification/storytelling/social/a11y/delight/retention/viral/premium/future), each scored effort × impact; top ~25 mapped into phases 3–7.
- Feature recommendations for the independent launch (shareable trip pages, seasonal themes, passport-stamp trip history, etc.) — flagged where they'd need logic changes (out of scope, listed for your v2).
**Components affected:** `packaging/` docs only.
**Complexity:** M. **Dependencies:** none. **Risks:** analysis paralysis — timeboxed; ideas must land in a prioritized backlog, not an essay.
**Testing:** n/a (document review).
**Done when:** you approve the strategy + prioritized backlog.
**NOT doing:** any code, any tokens, any mockups beyond low-fi sketches.

## Phase 3 — Design Language & Design System

**Goal:** the single source of truth every screen composes from — tokens + base components.
**Scope:** create `src/agent/templates/_tokens.html` (or `static/tokens.css`) + component partials; apply to nothing yet except a living style-guide page (dev-only route is out of scope — use a static preview HTML in `packaging/`).
**Features:**
- Token layer (CSS custom properties): color in OKLCH (day/dusk/night palettes; travel-warm neutrals replacing generic slate), type scale (display serif or humanist for "journal" voice + clean UI sans), spacing rhythm, radii, elevation/glass, motion tokens (durations/easings), z-layers.
- Base components (Jinja partials + classes): buttons, chips, cards, glass panel, section header, divider ("route line"), badge/stamp, skeleton loaders, focus ring standard.
- Motion primitives: reveal, drift, parallax hooks (CSS-first; GSAP via CDN only where CSS can't).
- Iconography + illustration direction (hand-crafted travel motifs — tickets, stamps, routes).
**Components affected:** `base.html` (token include), new partials; no behavior files.
**Complexity:** M–L. **Dependencies:** Phase 2 approval. **Risks:** Tailwind-CDN + custom properties interplay — resolved by tokens-as-CSS-variables consumed through arbitrary-value classes; over-designing components before real usage — build only what phases 4–6 need.
**Testing:** style-guide visual review, contrast checks on every token pair (axe), reduced-motion verification.
**Done when:** approved style guide; tokens power ≥1 real screen (the login page as pilot).
**NOT doing:** rolling tokens across all screens (Phase 4), 3D/sound, itinerary components.

## Phase 4 — Experience Architecture & Global UI

**Goal:** the whole app inhabits one continuous world — navigation feels like moving through places, not switching pages.
**Scope:** every non-itinerary surface: chat shell, header/nav, welcome/landing state, login, trips ("your journeys" — passport/stamp metaphor), profile, splash upgrade, empty/loading/error states, PWA icons/theme color.
**Features:**
- Chat as a place: horizon backdrop (CSS/SVG atmosphere layer v1 — sky gradient, drifting clouds, distant terrain silhouette), input redesigned as "where to next?" departure field, example chips as destination tickets, progress statuses as journey checkpoints ("Mapping your route…" with route-line animation), sign-in gate bubble redesigned warmly.
- First-visit landing moment: the greeting arrives as an invitation to travel, not a bot message.
- Trips page → "Travel Shelf": each saved trip a ticket/journal spine with destination, dates, stamp.
- View transitions between pages (View Transitions API, graceful fallback).
- Splash refined: the existing train, elevated (timing, steam, reduced-motion respect).
**Components affected:** all templates except itinerary internals of chat bubbles + `print.html`; `static/` assets.
**Complexity:** L. **Dependencies:** Phase 3 tokens. **Risks:** the 431-line `chat.html` — split into partials without touching its SSE/questionnaire JS behavior (verify byte-for-byte event handling survives); atmosphere layer perf on low-end mobile — layered degradation (static gradient → CSS drift → richer).
**Testing:** Chrome extension walkthrough of every route logged-in/out, mobile viewport, keyboard-only pass, axe on all pages, Lighthouse before/after, existing pytest suite green.
**Done when:** every screen speaks the design language; app feels like one world; deployed + verified.
**NOT doing:** WebGL/3D, sound, itinerary renderer, questionnaire visual overhaul beyond token reskin (its logic is subtle — full redesign rides with Phase 5 if needed).

## Phase 5 — Premium Itinerary Experience (the crown jewel)

**Goal:** the itinerary stops being a chat message and becomes a crafted, interactive travel journal.
**Scope:** a frontend **itinerary presentation layer**: detect a completed itinerary reply, transform its markdown into structured components. Generation, prompts, SSE contract untouched.
**Features:**
- Parser (vanilla JS module in `static/`): markdown → structure (trip title, days, time-of-day blocks, stays, food, transport, budget tables, tips/warnings) with **graceful fallback to plain markdown** when structure doesn't match.
- Journal components: trip hero (destination, dates, travelers, budget headline), day chapters with route-line timeline, morning/afternoon/evening scenes, stay & food cards, budget as elegant visual summary, tips/packing/warnings as stamps & notes, expandable details, sticky day navigator (mobile-first), beautiful day separators.
- Streaming behavior: stream as text (as today); on `done`, the finished reply gracefully transforms into the journal ("your journal is being written" moment). Non-itinerary replies stay conversational bubbles.
- Restored transcripts get the same transformation on load.
**Components affected:** `chat.html` (assistant-bubble rendering path only), new `static/itinerary.js` + partial templates; **no** planner files.
**Complexity:** XL — highest of the program. **Dependencies:** Phases 3–4. **Risks:** markdown shape variance across destinations/lengths — mitigate with fixture library (save 8–10 real replies as test fixtures: long/short/international/budget/edge) and always-safe fallback; re-parse perf — transform once on `done`, not per delta; double-render flicker — crossfade.
**Testing:** fixture-driven parser unit tests (pytest for any server bits, JS fixtures for parser), Chrome extension live runs against real plans (Kerala 5d, Japan 8d, Bali honeymoon…), regression: statuses/forms/errors still render, mobile scroll feel, axe (semantic headings, aria), Lighthouse.
**Done when:** a generated itinerary reads like a premium travel journal on desktop + mobile; all information preserved; fallback proven; deployed + verified.
**NOT doing:** changing what the agent writes, maps/photos requiring new APIs (flag as suggestions), PDF (next phase).

## Phase 6 — PDF, Sharing & Export System

**Goal:** a share-worthy, formal, premium PDF of the **final itinerary only** — no chat, no iterations, no animations.
**Scope:** redesign `print.html` + the path into it. Zero-dependency `window.print()` approach stays.
**Features:**
- Final-itinerary selection (presentation-side): latest assistant message that parses as a full itinerary = the export source. Clear empty-state when none exists.
- Formal document design: cover (trip title, destination, dates, traveler line), overview/quick summary, day-by-day sections, stay/transport/budget tables, notes/tips, closing summary; print-safe typography, page-break intelligence (`break-inside: avoid`), A4-optimized, static replacements for all animated elements.
- "Download PDF" affordance inside the itinerary journal (Phase 5 component) — not just a header link.
- Export architecture kept format-extensible (docx/markdown/share-page later, no logic changes needed).
**Components affected:** `print.html`, small addition in `chat.html`/journal component; reuses Phase 5 parser.
**Complexity:** M. **Dependencies:** Phase 5 parser. **Risks:** "final itinerary" heuristic ambiguity — reuse the proven parser + document the rule; browser print engine quirks — test Chrome/Safari margins & backgrounds (`print-color-adjust`).
**Testing:** print-preview across browsers/paper sizes via Chrome extension, multi-iteration trips (verify only final exports), long trips (page breaks), information-completeness diff vs. raw markdown.
**Done when:** a family-shareable, premium formal PDF from any finished trip; deployed + verified.
**NOT doing:** server-side PDF generation, emailing/sharing infrastructure, watermarks/branding beyond the document design.

## Phase 7 — Motion, Sound, Delight & Launch Polish

**Goal:** the living world comes fully alive — the memorable layer people share.
**Scope:** ambient world v2 + audio + micro-interaction sweep + launch-page polish. All opt-in/degradable.
**Features:**
- World v2: time-of-day progression (sunrise→dusk→stars), weather moods, birds/balloon/passing train or plane as rare delight moments (not loops), possibly a lightweight WebGL layer (Three.js via CDN) **only if** the CSS/SVG world can't reach the bar and perf budget allows.
- Sound system: Web Audio ambient beds (wind, birds, distant station), UI ticks (stamp thunk on save, ticket tear on new trip), master mute, default respectful (off or whisper-quiet until user opts in), `prefers-reduced-motion`/data-saver respected.
- Micro-interaction sweep: hover/press states, form focus choreography, send-button departure moment, questionnaire chips polish, skeletons everywhere something loads.
- Delight moments from the Phase 2 backlog (top-scored, e.g. passport stamp when a trip is saved).
**Components affected:** templates + `static/` (audio sprites, world layer); nothing frozen.
**Complexity:** L–XL (depends on WebGL go/no-go — decided with you mid-phase). **Dependencies:** Phases 3–5. **Risks:** perf regression — hard budget gates, feature-detect + tiered rendering; annoyance — sound strictly opt-in; scope creep — only backlog items approved in the phase vision.
**Testing:** low-end device throttled runs (Lighthouse + DevTools CPU throttle), 60fps traces, reduced-motion/no-audio paths, battery/CPU sanity, full-app regression via Chrome extension.
**Done when:** the world breathes, nothing lags, everything degrades; deployed + verified.
**NOT doing:** gamification systems, social features, seasonal live-ops (v2 candidates).

## Phase 8 — Performance, Accessibility & Production Readiness

**Goal:** launch-grade: fast, accessible, robust, SEO-ready.
**Scope:** audit + fix across the whole app; no new features.
**Features:**
- Perf: Core Web Vitals pass on mid-range mobile; asset audit (compress, lazy-load, font strategy); evaluate precompiled Tailwind vs. CDN runtime (**decision surfaced to you** — it touches the no-build rule); cache headers/service-worker review (presentation assets only).
- A11y: full WCAG 2.2 AA sweep (axe + manual keyboard + screen-reader pass on chat, journal, forms, PDF flow); aria-live for streaming; focus management on transforms.
- SEO/launch: meta/OG/social cards (shareable = viral), landing crawlability, manifest polish, error pages with personality (lost-luggage 404).
- Production hygiene: cross-browser matrix (Chrome/Safari/Firefox/Android/iOS), offline/slow-network behavior, final content/copy proof.
**Components affected:** templates, static; possibly `pyproject`/deploy config only if a CSS pipeline is approved.
**Complexity:** L. **Dependencies:** all prior phases. **Risks:** late a11y findings forcing rework — mitigated because every phase already ran axe gates; this is the sweep, not the first look.
**Testing:** Lighthouse ≥90 perf/a11y/best-practices/SEO targets, axe zero critical, full scenario walkthroughs, pytest suite green, deployed prod verification.
**Done when:** all gates green on production; TravelOS is launch-ready as an independent product.
**NOT doing:** feature additions, planning-logic changes, marketing site.

---

## Sequencing logic & rework minimization
Tokens (3) before screens (4) before the journal (5) so nothing is styled twice. The journal
parser (5) is deliberately built before PDF (6) so export reuses it instead of a parallel
parser. The world layer (7) lands after the core product is premium — delight decorates a
solid product, never masks a weak one. The a11y/perf sweep (8) is cheap because every phase
carried its own QA gates.

## Standing suggestions surfaced (logic-adjacent, need your explicit go-ahead someday)
1. Structured itinerary output (agent emits a JSON block alongside markdown) — would make the
   journal & PDF bulletproof. Small prompt/tool change; deliberately NOT done in this program.
2. Public shareable trip page (`/trip/{id}/share` read-only route) — new route = logic.
3. Precompiled Tailwind (build step) — Phase 8 decision.
