# Scenarios

**Stage 3 — Concrete end-to-end walkthroughs.** These become the test checklist for
stage 8. Real inputs, expected results.

**This file is Layer 3 of the TripOS quality model** (unit → integration → **scenario
validation**; see the permanent "Scenario Validation Is A First-Class Quality Gate" section in
`policy.md`). Running these cases LIVE and comparing against the written expectations is a
**mandatory release gate**, not optional QA — every new capability adds its scenarios here
**before** implementation, and a feature isn't complete until they pass against the real
system, whatever the automated tests say.

## Happy path

**Scenario: Priya plans a family trip to a known destination.**
1. User picks **Plan a Destination** and answers: destination **Munnar**, from **Chennai**, **5 days**, **Family with Senior Citizens**, budget **₹50,000**, interests **Nature + Food + Sightseeing**, food **Vegetarian**.
2. The agent fills any gaps with at most a question or two, then proposes a **complete plan on one screen**: transport (train Chennai→Aluva + pickup), stays (Munnar 2 nights + Thekkady 2 nights), food plan, attractions **clustered by base** to cut backtracking, an itemized budget (~₹30,000) with a confidence %, and travel-intelligence badges (season, crowd, weather, fatigue, feasibility).
3. The user ends up with a feasible, *explained* plan within budget, then clicks **Generate Final Itinerary** for a day-by-day schedule, and **Saves** + **Exports** it.

**Expected result:** Total cost shown as a number **and a range**, within the ₹50,000 budget; pace marked relaxed (suitable for seniors); ≤ 2 follow-up questions; every section has a one-line "why".

## Edge cases & tricky inputs

- **Discovery (no destination):** from **Chennai**, **₹25,000**, **3 days**, **Nature + Adventure** → expected: **3 ranked suggestions** (e.g. Munnar / Kodaikanal / Yercaud), each with a one-line reason and all reachable + affordable from Chennai in 3 days; user picks one and the normal flow continues.
- **Unrealistic itinerary:** "Munnar + Thekkady + Kodaikanal in 2 days" → expected: agent calls it unrealistic, shows the travel-time math, and suggests one base or more days.
- **Over budget:** 5-day trip for 4 people on **₹8,000** → expected: agent says it isn't feasible once travel + stay are counted, states a realistic floor, and offers a shorter or closer option.
- **Worldwide planning (updated 2026-06-06 — supersedes the old "India only" case):** "Plan me a trip to **Paris**" → expected: planned like any other destination via retrieval (no fabricated data, estimates labelled). A place that genuinely can't be found → ask to check the spelling or name a nearby well-known town, naturally.
- **Vague input:** "I want to go somewhere nice" → expected: **one** friendly clarifying question (start city or budget), not a form.
- **Bad weather / service down:** dates in peak monsoon (or weather API unavailable) → expected: flags heavy rain, swaps trekking/safari for indoor-friendly spots (Tea Museum, Spice Plantation); if the API is down, falls back to seasonal norms and says so.
- **Mid-plan change:** "reduce budget to ₹35,000" → expected: swaps stays/activities to fit while keeping destination + dates, then shows the new total and **what changed**.

## Seasonality (added 2026-06-06)

- **Suboptimal month — user continues:** "5 days in **Dubai in July**, from Mumbai, couple, ₹1,00,000/person, sightseeing + food" → expected: **before any itinerary appears**, a short travel advisory (extreme heat, most outdoor sightseeing uncomfortable), the recommended window (**Nov–Mar**) with a one-line why, and a friendly choice: keep July or look at a better window. User says "continue with July" → the plan is generated **immediately** (no re-warning), leans **indoor + evening** (malls, aquarium, museums, desert activity in the evening, night souks; no midday outdoor blocks), and opens with a **Travel Context** note saying the plan was shaped for July conditions.
- **Suboptimal month — user shifts:** same trip, user answers "okay, December instead" → expected: plan generated for **December**, outdoor stops back in play; Travel Context names December.
- **Good month — no friction:** "**Munnar in January**" (post-monsoon, pleasant) → expected: **no advisory step at all** — straight to the plan, which still opens with the Travel Context note (month, expected weather, season) so the traveler always sees timing was considered.
- **Flexible timing:** "not sure when — whenever is best" → expected: travel month is treated as answered; TripOS recommends the best window for the destination with a one-line why and plans for it.
- **Exact dates given:** "Dec 20 to Dec 27" → expected: dates are kept with the trip (for future booking), seasonality is assessed for **December**, and the traveler is never asked to repeat or refine dates.
- **Trip spans two months:** "Dec 28 to Jan 4" → expected: both months assessed; if they differ, the more cautious verdict leads, with a note on which part of the trip it affects.
- **Season data unavailable:** an obscure destination where research finds nothing solid about seasons → expected: **no bluffed advisory** — plan proceeds normally and the weather section honestly says seasonal conditions couldn't be confirmed.

## Budget as a constraint (added 2026-06-06, Phase A)

- **Fits after economizing:** ₹50,000/person, 5 days, balanced — first assembly with mid-tier stays lands slightly over → expected: the engine **automatically uses budget-tier stays**, the final estimate lands within ₹50k, the recommended stay shown first is the affordable one, and a one-line note says the stay tier was chosen to fit the budget. **No advisory needed.**
- **Can't fit — advisory:** a trip whose realistic floor is well above the budget even at budget-tier stays (e.g. ₹50k for a trip estimating ₹72–80k) → expected: **before** presenting it as final, a clear advisory — estimate range vs budget, plus the levers (fewer days / simpler stays / different destination / raise budget) — and the question "want me to optimize, or keep it as is?" **Wait for the answer.**
- **User accepts over-budget:** after that advisory the user says "keep it anyway" → expected: full plan presented immediately with the honest estimate; **no re-warning**.
- **Luxury conflict:** interests include **luxury**, budget ₹30,000 for 5-day Goa → expected: **no silent downgrade to budget stays** — an advisory naming what luxury actually costs there, asking whether to adjust budget, style, or destination.
- **Budget-ranked circuits:** "6 days in Kerala, ₹30,000/person" → expected: routes presented **best-budget-fit first**, each labelled (e.g. "fits your budget" / "a stretch" / "premium"), not popularity-ordered.
- **Generous budget:** ₹2,00,000/person for the same trip → expected: no pointless economizing — mid/premium stays recommended, headroom mentioned, still honest estimates.
- **Honest presentation (any plan):** the budget shows a **rounded range** as the primary figure (never "₹18,835"), a confidence level (high/medium/low) **with its reason**, the ✓/⚠/❌ feasibility verdict, and a short "based on / varies with" note.
- **Flight question:** "how much will flights cost?" → expected: a typical-pattern **range** ("usually ₹12,000–₹18,000 return for this route and month"), explicitly an estimate — never an exact fare.
- **No month given (flexible):** estimate still produced → expected: confidence drops (month unknown → wider seasonal swing) and the reason says so.

## Preferences as constraints (added 2026-06-06, Phase B)

- **Non-touristy Paris:** "4 days in Paris in May, non-touristy — hidden gems and local life. Couple, ₹1,50,000/person, food + photography." → expected: the itinerary **leads with lesser-known neighbourhoods, markets, viewpoints**; Eiffel Tower / Louvre don't headline; the presentation says the plan was shaped for hidden-gem character.
- **Classic first-timer:** "First time in Paris — the classic highlights please." → expected: icons (Eiffel, Louvre) front and centre; no "personalization" hiding them.
- **Avoid list:** "Plan Jaipur, but no forts please." → expected: no fort stops anywhere in the plan; everything else normal.
- **Mixed preference:** "Hidden-gem Agra, but obviously include the Taj Mahal." → expected: Taj is in (explicit request wins), the rest of the plan leans offbeat.
- **Preference on a curated destination (no popularity data, e.g. Munnar):** → expected: plan still builds; preference applied only where data allows; **no claim** of hidden-gem optimization that didn't happen.

## Intent-driven service (V2 Intelligence Upgrade, added 2026-06-06)

Not every message is a trip-planning request. The agent must first understand what the
traveler is actually trying to accomplish — find a place to stay, find somewhere to eat,
decide where to go, plan a full trip, or just get advice — and serve **that**, with the
fewest possible questions. A stay/restaurant/destination request must **never** trigger
itinerary questions.

- **Homestay search (FIND_STAYS):** "Suggest homestays in **Didupe** under **₹10,000** per person."
  → expected: **no itinerary questions** (no duration / travel style / pace / start city);
  a **recommended homestay + 2–3 alternatives**, each with a ₹/night **range** (estimates,
  never exact), why it's recommended, review quality where known, and a one-line tradeoff.
  If the village genuinely has fewer matching options, say so honestly and show the closest
  alternatives — **never invent properties**. No "search Airbnb / Booking.com" deflections.
- **Restaurant search (FIND_RESTAURANTS):** "Best **seafood** restaurants in **Kochi** for a
  romantic dinner." → expected: no slot-gathering; a recommended spot + 2–3 alternatives with
  cuisine, price band, area, why, and the occasion respected. Never "check Zomato / Google Maps".
- **Destination discovery (DISCOVER_DESTINATIONS):** "Where should I go for **5 days in
  December**? Beaches, **₹40,000**/person, from Chennai." → expected: **3–5 ranked destination
  ideas, best budget fit first**, each with a one-line why, the season fit for December, a rough
  per-person budget range, and a tradeoff; then an offer to plan whichever they pick. No
  unnecessary questions — days, month, budget, and interests are already given.
- **Immediate travel (Travel Context):** "I'm **leaving today** for Kerala for 5 days." →
  expected: today's actual date is resolved automatically — travel month, season, and
  immediate-travel mode follow from it **without asking when they're travelling**; the agent
  proceeds with sensible defaults for anything minor that's missing rather than interrogating.
  Same for "tomorrow", "next weekend", "this December": resolved against today's date, never
  asked back.
- **Relative date in any intent:** "Homestays in Wayanad **next weekend** under ₹5,000/night."
  → expected: FIND_STAYS served directly; "next weekend" resolved to real dates internally;
  no questions.
- **PLAN_TRIP unchanged (regression):** "Plan a 6-day Kerala trip for ₹40,000 per person." →
  expected: the existing full planning flow exactly as documented above — gathering the missing
  essentials (briefly, inferring everything already stated, never re-asking), season check,
  budget-as-constraint, advisories. The hidden-gem Paris, Dubai-in-July, budget-advisory, and
  no-forts scenarios above must all still behave **identically** after this upgrade.
- **Aggressive inference (PLAN_TRIP):** "Plan 4 days in Goa with my wife in November, ₹30k each,
  we love food." → expected: group (couple, 2 people), month (November), days, budget, and
  interests (food) are all **inferred from the message** — at most one short follow-up for
  what's genuinely missing (start city), never a re-ask of anything stated.

## Responsiveness & voice (added 2026-06-06)

Speed without quality loss: same models, same retrieval, same plans — work just starts earlier
(prewarming during the conversation) and progress is visible while it runs. Progress updates
must be HONEST — a stage is shown ✓ only when that work actually completed.

- **Live progress checklist:** any full build ("plan 5 days in Munnar…", all details given) →
  while the plan is being built, the status area shows a **growing checklist** (e.g.
  "✓ Destination intelligence retrieved → ✓ Stays & restaurants found → • Building your
  day-by-day…"), never one frozen "Building your trip…" block for the whole wait.
- **Prewarmed final turn:** a conversation where the destination + month are known early (so the
  season check ran) and the traveler then answers the remaining questions → the build turn
  starts producing the plan **much faster than a cold build** (retrieval was warmed during the
  conversation). The plan content is **identical** to what a cold build produces.
- **Digging-deeper stage:** a niche stay ask in a small place ("homestays in Didupe…") that
  needs the focused second retrieval → the status honestly shows a deeper-search stage rather
  than silence during the extra wait.
- **Multi-leg progress:** a circuit build shows each leg completing ("✓ Planned Munnar (1/2)").

Voice input (manual browser checks — Chrome/Edge/Safari):
- **Transcribe, don't send:** press mic, say "Plan a five day Kerala trip in December" →
  the text appears **in the input box**, the message is **NOT sent**; Send remains manual.
- **Append, never replace:** with "Plan a Japan trip." already in the input, record "Eight
  days." → input becomes "Plan a Japan trip. Eight days." (previous text intact, ". " joining);
  a third recording appends again.
- **Fully editable — and edit intent stops the mic (updated 2026-06-07):** the input is
  NEVER read-only. Tapping into the transcript or typing **while recording** stops the mic
  and hands over a normal text box — cursor lands where tapped, the keyboard opens (mobile),
  words can be edited/deleted/selected/pasted. Example: speak "…trip to Bangalore…", tap
  "Bangalore", change it to "Mysore" — works on a phone exactly like on desktop.
- **Mic state is obvious everywhere (added 2026-06-07):** idle = a muted mic-with-slash
  ("tap to start speaking"); listening = an open mic with a red glow/pulse ("I'm
  listening"). The two states are visually distinct on mobile, tablet, and desktop; stopping
  returns the muted icon with the transcript intact and editable, never auto-sent.
- **Graceful degradation:** in a browser without speech recognition (e.g. Firefox) the mic
  button simply isn't shown; typing and everything else works unchanged.
- **Mobile transcript integrity (added 2026-06-07, after a live-caught Android bug):** on
  Android Chrome / iOS Safari, saying "Plan a 5 day trip to Bangalore with my parents" must
  produce that sentence ONCE — never the cumulative ladder ("plan… plan a… plan a 5…").
  Interim text visibly REPLACES itself while speaking; a natural pause mid-recording does
  not stop the mic (the engine restarts silently and the finished phrase is kept); tapping
  stop ends it. The engine's results list is the only transcript state — no client-side
  accumulation.

## Questionnaire-first planning (added 2026-06-07)

*(Supersedes the "one question at a time" gathering style for PLAN_TRIP — a user-directed
reversal of the 2026-06-06 "pure chat" decision. Goal: 1 prompt + 1 questionnaire +
1 submission → plan. Chat always remains available alongside the form.)*

- **Smart form, only the gaps:** "Plan a 4-day trip to Coorg from Chennai for 2 people." →
  ONE questionnaire block appears in the chat asking ONLY what's missing (dates, budget,
  interests) — destination/origin/duration/travelers are echoed in its header ("Got it:
  Coorg · 4 days · 2 people"), **never re-asked**. No field-by-field text questions.
- **One submit → plan:** filling the form (tap-chips for choices, multi-select interests,
  typed budget, month picker with a "Flexible" option) and pressing **Build my trip** leads
  straight to the plan — the live "my understanding" strip inside the form is the
  confirmation; no extra round-trip, no further text questions for answered fields.
- **Branching:** choosing style "Road Trip" reveals self-drive + max-driving-hours
  sub-questions; "Luxury" reveals resort/fine-dining; "Budget" reveals hostel/shared-transport
  acceptability. Irrelevant branches never appear.
- **Challenging month still advises:** form submitted with July for Dubai → ONE season
  advisory turn (keep or shift?), then the plan on confirmation — the advisory is deliberate
  product behavior, the only legitimate post-form follow-up.
- **Conflict is asked, never silently resolved:** form said ₹15,000, then the user types
  "actually I can stretch to ₹30,000" → the agent asks one line ("which budget should I
  use?") and uses the answer.
- **Chat override (hybrid):** the user ignores the form and answers in plain text → the agent
  proceeds from the text; the unused form simply stays behind, irrelevant.
- **CLI fallback:** in the terminal (`uv run agent`, no form UI) the same situation produces
  a compact bullet-list question in text — never an error.
- **Cold season check is fast (split extraction):** a season check on a destination nobody has
  asked about recently completes in roughly a third of the old time (seasonality is extracted
  first; stays/food/weather finish in the background) — with **identical verdicts** and all
  enrichment slices still populated for the build that follows.
- **Concise replies:** plans lead with the itinerary; same facts, ranges, and honesty
  contract — noticeably tighter prose.

## Accounts & entry (added 2026-06-07 — supersedes the shared-password gate)

Authentication exists only to save trips, restore conversations, and protect user data —
planning stays the product. Passwordless only: Google or email magic link; Login and Sign Up
are the same mechanism (the system decides new-vs-existing after auth; one account per email,
ever).

- **Logged-out browsing:** opening TripOS shows the chat (greeting, examples, input) with
  Login / Sign Up top-right — no marketing page, no wall. Attempting to SEND shows
  "Sign in to start planning and save your trips" with a way into login. Nothing is planned,
  nothing is spent, no trip row is created.
- **Email verification code (new user):** enter email → "Send Verification Code" → the
  SAME message whether or not the account exists (no enumeration) → a 6-digit code arrives →
  enter it (mobile keyboards autofill it) → Verify → asked once "What should we call you?" →
  enters TripOS.
- **Email verification code (returning user):** same flow, no name question, straight to chat.
- **Code rules:** 6 digits, expires in 10 minutes, works exactly ONCE, bound to the email it
  was sent to. Requesting a new code invalidates the old one. After 5 wrong attempts the code
  is dead and a new one must be requested.
- **Resend cooldown:** after sending, "Resend code in 40s" counts down; at 0 it becomes
  "Resend Code" (a new code, fresh countdown). The cooldown is enforced server-side too.
- **Specific errors, never generic:** wrong code → "That code isn't right"; expired → "That
  code expired — send a new one"; too many tries → "Too many attempts — request a new code";
  provider/send failure → "We couldn't send the email right now — try again in a minute"
  (a SYSTEM failure is surfaced honestly, never hidden behind 'Check your email').
- **Persistent session:** sign in once → return tomorrow / next week / next month still
  signed in (90-day rolling). Logout, or a long absence, requires signing in again.
- **Google (when configured):** "Continue with Google" → pick account → straight in; name,
  email, photo imported automatically; an existing email account just logs in (no duplicate);
  an unverified Google email is refused (never merges into someone's account).
- **Isolation (hard requirement):** Saved Trips shows ONLY my trips. Opening another user's
  trip URL (including its /print view) → 404, indistinguishable from non-existent. A stale
  trip cookie from another account on this device opens a FRESH trip, never theirs.
- **Legacy claim:** the first account ever created automatically owns all pre-auth trips
  (the founder's testing history); the second account owns nothing it didn't create.
- **Logged-in nav:** TripOS left; New Trip · Saved Trips · avatar right; avatar menu shows
  picture/name/email, Edit Profile, Saved Trips, Settings, Logout. Profile allows editing
  name and uploading a photo (email read-only).

## Splash & app feel (added 2026-06-07; manual browser checks)

- **First visit:** branded splash ≤4s — monochrome "TripOS / Your AI Travel Partner" upper-
  middle, minimal railway track near the bottom, a vintage steam locomotive crossing left→
  right, steam rising white→brand colors carrying destination names (Kyoto, Bali, Paris,
  Santorini, Munnar, Ladakh…), the steam visibly "painting" the logo to full color, then a
  smooth fade into the chat. Silent. No hard cuts.
- **Return visits:** only a 0.5–1s logo reveal + quick sweep — the app opens essentially
  immediately. Users with reduced-motion set get the quick variant always.
- **PWA:** visiting on Chrome/Android offers Install (native prompt once criteria met);
  iOS Safari users can Add to Home Screen; the installed icon opens TripOS standalone,
  feeling like an app. Lighthouse PWA installability passes.

## Done = all scenarios pass

When every scenario here behaves as written, V1 works. Add new cases as we discover them,
then make them pass.
