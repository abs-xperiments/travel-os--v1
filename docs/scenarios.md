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

## Done = all scenarios pass

When every scenario here behaves as written, V1 works. Add new cases as we discover them,
then make them pass.
