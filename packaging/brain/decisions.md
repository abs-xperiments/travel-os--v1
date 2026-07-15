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

## 2026-07-15 — World v2 — The Worldscape overture (WebGL approved by user)
- **Chose:** a scroll-driven Three.js flight (floating islands → balloon → train viaduct →
  horizon) as a landing OVERTURE on fresh chats, with oversized Fraunces storytelling type.
  Supersedes the earlier "no WebGL for v1" call — the user explicitly requested the
  immersive 3D treatment. Buildless: Three.js 0.160 via CDN importmap; procedural geometry
  only (no asset downloads); transparent canvas so the CSS hour-palette carries the sky.
- **Over:** replacing the chat page with a separate 3D landing route (new route = logic,
  forbidden) and scroll-jacking the chat itself (usability).
- **Guardrails:** mounts ONLY when fresh chat + WebGL available + no reduced-motion + not
  already flown this session; Skip button, Escape key, and scroll-to-end all land in the
  chat; ANY load/init error removes the overlay silently. Pixel ratio capped at 1.6; one
  light pair, fog, ~low-poly everything; renderer disposed on exit.
- **Affects:** the overture is additive — chat, journal, and PDF are untouched beneath it.

## 2026-07-15 — World v3 — Presence over spectacle (supersedes the stylized overture)
- **Chose:** the landing journey is now CINEMATIC PHOTOGRAPHY of real Earth — sunrise
  valley, alpine ridgelines, forest light, still backwaters, aurora — with a documentary
  camera (slow push-ins, incommensurate-sine hand-held drift, heavy easing), drifting fog
  banks, film grain, vignette, and per-scene atmospheric grading. Three.js dropped from
  the overture entirely: real imagery IS how presence is achieved on the web (Apple-style),
  and it's ~300KB lighter than the 3D lib alone.
- **Over:** pushing the low-poly world toward photorealism (uncanny, heavy, still
  game-like) and full PBR/HDRI WebGL (browser-realistic only with big streamed assets —
  deferred to the vision's Phase 5 "advanced experiences" tier for capable devices).
- **Guardrails kept:** fresh chat only, once per session, reduced-motion + Save-Data
  respected, skip/Escape/scroll-end land in the product, 4s first-frame budget or the
  overlay yields, later scene failures degrade to a shorter journey.
- **Assets:** Unsplash CDN hotlinks (supported use, license-clean), all 5 URLs verified
  reachable; scene swap = edit SCENES in worldscape.js. Founder should eyeball scene 4
  (intended: Kerala backwaters) and swap if the mood is off.
- **Affects:** worldscape.js/css rewritten; chat.html overlay markup updated; no importmap.

## 2026-07-15 — World v4 — Fantasy restored and perfected (user direction, supersedes v3)
- **Chose:** the founder flew both and preferred the fantasy dreamscape — restored the
  Three.js flight and enhanced it: low-sun horizon glow that dims into night, rippling
  valley lake, fireflies (skipped on <4GB devices), pooled steam puffs from the locomotive,
  an aurora ribbon that unfurls as a DOM night-veil deepens (progress-driven day→night),
  occasional unpredictable meteors, camera that banks into turns via path tangent + subtle
  FOV breathing, frame-rate-independent glide damping (1-0.01^dt), ws-ready first-frame
  fade-in.
- **Over:** keeping the photographic presence engine (felt less smooth/immersive to the
  founder — taste decision, theirs to make) and mixing both (incoherent).
- **Kept from v3:** breathing typography, vignette optics, Save-Data guard, ws-ready
  pattern, all escape hatches. Unsplash scenes removed; zero external image dependencies
  again.
- **Affects:** worldscape.js/css + chat.html overlay rewritten; importmap back; preview
  updated. The photographic engine survives in git history if ever wanted.

## 2026-07-15 — World v5 — The world becomes the product (explorable, dual-entry)
- **Chose:** scroll-journey and hero copy removed — the founder's insight: the world was
  asking users to explore while the UI asked them to read. Arrival is now the world plus
  two doors ("🌍 Explore the world" / "✈️ Plan my trip", equal citizens, Plan visually
  primary and persistent while exploring). Exploration is a data-driven LANDMARKS registry:
  each entry declares anchor/camera-offset/gaze/one-line whisper/optional follow() — the
  isles, balloon, train, lake and sky are click-to-fly destinations; train and balloon are
  RIDES (camera travels with them). Camera flights are arced bezier tweens with cinematic
  easing; overview has idle drift + pointer parallax + drag-to-look that relaxes home.
  Adding a future destination = one registry entry, zero engine changes.
- **Also:** white-oval clouds replaced with layered elongated clusters; floating lanterns
  glow up at night; ambient ~4-minute day↔night cycle whose phase starts from the page's
  data-sky hour; sky dial added to the chat header (auto/dawn/day/dusk/night, persisted,
  base.html honors the override) — the dawn/dusk modes are now a visible, playable feature.
- **Over:** keeping the text-section scroll journey (reads as "landing page with a nice
  background") and free-flight camera controls (game-like, motion-sickness risk).
- **Escape hatches:** Plan CTA always on screen, Escape lands, #explore hash lets
  returning users re-enter the world, all mount guards unchanged.
- **Affects:** worldscape.js is now an exploration engine (547 lines — accepted slight
  overage of the ~500 rule; splitting builders into a second module would cost an extra
  request for no clarity gain, noted here deliberately).

## 2026-07-15 — World v6 — Back to the painted scroll-journey (final direction, supersedes v5)
- **Chose:** the founder settled the direction: the ORIGINAL scroll-flight is the product's
  landing experience — one journey, one "Skip to planning" button, scroll-to-end lands in
  the chat. No explore mode, no click-to-fly, no dual doors. Enhanced into a digital-
  painting fantasy: extended flight path (mountains → valley & train → pine forest & lake →
  palm-lined shore → open ocean into night + aurora), instanced pine forest planted on the
  real terrain heightfield, shoreline where land melts into sand (smoothstep blend), an
  animated ocean with a sun-path glow, palms, a breaching whale, butterflies, and the
  saturated painterly palette (violet haze fog, warmer snow, deeper greens).
- **Kept from later versions:** layered cloud clusters (the white-ovals fix), banking
  camera + framerate-independent damping, breathing typography, night veil, sky dial in
  the chat header, all mount guards and escape hatches.
- **Removed:** LANDMARKS registry, raycasting, drag-to-look, entry doors, place chips,
  #explore hash (all live in git history if ever wanted).
- **Affects:** worldscape.js/css + chat overlay rewritten; 503 lines, back inside the
  ~500 rule.

## 2026-07-15 — Review fixes — Sanctioned prompt exception + one layer scale
- **Chose:** (a) a two-sub-case DISCOVER rule in prompt.py — the founder's review explicitly
  ordered reconnecting Discover to the existing Tap-In cards; the edit reuses
  request_trip_details/the bank/the form channel with zero new code paths, and constrained
  discovers still answer instantly. (b) The header owns z-30 and theme.css documents ONE
  app-wide layer scale — because .glass's backdrop-filter creates stacking contexts, any
  surface without an explicit layer is at the mercy of DOM order.
- **Over:** (a) frontend-only interception of "discover" clicks (fragile string matching,
  duplicates onboarding logic — violates single source of truth); (b) arbitrary big
  z-indexes on the menu (whack-a-mole) or a JS portal layer (overkill for one dropdown —
  noted as the upgrade path if real modals arrive).
- **Affects:** prompt changes remain exceptional and founder-sanctioned only; all future
  overlays must pick a documented layer, never invent one.

## 2026-07-15 — World v7 — The narrative journey: explore → discover → meet → plan
- **Chose:** the landing is now a story with an earned introduction. Islands and balloon
  removed (atmosphere over floating geometry); the forest is three species with per-instance
  scale/tint/rotation and noise-carved clearings + glowing undergrowth (handcrafted feel =
  variation, not assets); a new snow chapter (peaks raised in the shared heightfield, cold
  hemisphere light, regional snowfall, five tiny trekkers walking a CatmullRom ridge trail);
  the lake replaced by the dream metropolis (instanced towers with emissive window texture,
  landmark spires with beacons, city haze, aerial trams on sine lanes); the flight then dips
  BENEATH the ocean where a deep veil turns into the planning theme's ink and the mythical
  diver-guide (dark suit, glowing visor, gold tank, halo, rising bubbles) introduces TripOS
  with staged lines and the single Begin button. The greeting chat bubble is gone from the
  landing — the world and the guide make the introduction (greeting still serves transcripts
  and non-visual clients; a "discover" link in the hero preserves that affordance).
- **Engineering:** split into worldscape.js (engine, 316 lines) + worldscape-scenery.js
  (builders, 401 lines) to honor the ~500 rule; instancing everywhere (forest/towers),
  region-gated particle updates (snow only near the peaks), LOW tier trims counts;
  sections are data-at positioned (chapters own coordinates, not even spacing).
- **Over:** a separate reveal page (route change — forbidden) and skipping the underwater
  act (the guide emerging from another world IS the brand moment the founder asked for).
- **Escape hatches unchanged:** skip/Escape land instantly; scroll-to-end now triggers the
  meeting rather than an abrupt exit; Begin lands in the chat.

## 2026-07-15 — Tap-In v2 — Cards everywhere, freedom at the end, PDF per destination
- **Chose:** (a) destination-only → cards, spelled out in the intent list itself (the model
  had room to interpret; now it doesn't). (b) When = exact From/To dates only, auto-filling
  the days answer live via a fieldInputs registry — one source of truth, user can still
  override the number. (c) Every form ends with a free-text + mic "anything else" section
  composed into the same submit message — freedom without new channels. (d) `meals` added
  to the question bank (stay/eatery spending style is a budget-shaping fact). (e) Every
  recommended stay/restaurant is a Google-search markdown link (name+city, new tab) — the
  traveler verifies reviews in one tap without us scraping anything. (f) PDF keeps the last
  itinerary per distinct destination (title-derived key): iterations collapse, real
  multi-trip chats export fully with Journey dividers.
- **Over:** parsing form answers server-side (conversation stays the single source of
  truth), a separate mic pipeline (reused SpeechRecognition pattern), and Google Maps/Places
  deep links (search links are stable, language-agnostic, and need no API).
- **Affects:** questionnaire bank copy is now traveler-facing UX writing — edit with care;
  the PDF destination key depends on journal titles leading with the destination.

## 2026-07-15 — Bug fixes — One dictation engine; calendar glyph un-cancelled
- **Chose:** extracted the chat mic's transcript architecture into window.TripVoice and
  made it the ONLY dictation path (chat input + questionnaire extras) — duplication was
  a re-implementation bug, and the cure is never re-implementing. Calendar indicator:
  color-scheme:dark + NO filter + gold chip backdrop (the previous invert() flipped the
  already-light native glyph back to dark — self-cancelling fixes are why root-cause
  notes matter). SW cache bumped to v3 so the fix can't be masked by stale CSS.
- **Affects:** any future dictation target must call TripVoice.attach — adding another
  raw SpeechRecognition handler is a regression by definition.

## 2026-07-15 — URL reliability + World v8 (the finalized fantasy)
- **URLs:** the agent invented "rohtangpermits.nic.in" in a Manali plan — trust-breaking.
  New prompt policy: NEVER invent/guess/reconstruct URLs. Stays/eateries → always
  Google-search links; attractions → no link or search-link (official site only if
  certain); permits/official bookings → search-link "X permit official" unless the
  official URL is certain. Accuracy beats appearing complete.
- **World v8 root-cause:** v7 read as "flat green" because the camera flew HIGH over
  SMALL trees and snow came mid-journey where altitude peaked. v8: the founder's final
  arc — snow peaks FIRST with the camera weaving low between summits (corridor carved
  into the heightfield), diffusing into a forest of trees 2× taller that tower over the
  camera with deer grazing in clearings, into the night metropolis flown down its avenue,
  onto a real beach (palms + breathing surf foam), skimming the waves, then under — where
  the guide is now the TRAVELER'S GENIE (luminous spirit, welcoming arms, wisp tail, gold
  sash, orbiting sparks). All region transitions are overlapping smoothsteps in ONE
  heightfield + position-lerped light — diffusions, never cuts. Sections are bold
  narrative only ("Begin where the air is thin…").
- **Affects:** worldscape v8 declared FINAL by the founder's brief; future changes are
  tuning, not redesign.
