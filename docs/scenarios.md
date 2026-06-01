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
- **Out of scope:** "Plan me a trip to **Goa**" → expected: honest "V1 covers Munnar, Thekkady, Kodaikanal, Wayanad, Yercaud — Goa isn't in yet. Want one of these?" (no fabricated Goa data).
- **Vague input:** "I want to go somewhere nice" → expected: **one** friendly clarifying question (start city or budget), not a form.
- **Bad weather / service down:** dates in peak monsoon (or weather API unavailable) → expected: flags heavy rain, swaps trekking/safari for indoor-friendly spots (Tea Museum, Spice Plantation); if the API is down, falls back to seasonal norms and says so.
- **Mid-plan change:** "reduce budget to ₹35,000" → expected: swaps stays/activities to fit while keeping destination + dates, then shows the new total and **what changed**.

## Done = all scenarios pass

When every scenario here behaves as written, V1 works. Add new cases as we discover them,
then make them pass.
