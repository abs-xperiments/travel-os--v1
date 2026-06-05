# Scenarios

**Stage 3 — Concrete end-to-end walkthroughs.** These become the test checklist for
stage 8. Real inputs, expected results.

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
- **Out of scope:** "Plan me a trip to **Paris**" → expected: honest "TripOS plans trips within India — Paris is out of scope. Want a similar Indian destination instead?" (no fabricated data). Same for an Indian town not yet in the catalog.
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

## Done = all scenarios pass

When every scenario here behaves as written, V1 works. Add new cases as we discover them,
then make them pass.
