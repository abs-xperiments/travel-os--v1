# Failure Modes

**Stage 3 — Operationalize *failure* as UX.**

For an AI travel planner, the worst outcome isn't an error message — it's a *confident,
plausible, wrong* plan the user trusts and acts on. These are the ways that happens and
how TripOS should fail **gracefully and honestly** instead.

## For each likely failure

| What could go wrong | How likely / how bad | How the agent should handle it |
|---------------------|----------------------|--------------------------------|
| Model **invents** a price, opening hour, or attraction | high / bad | Prefer the curated seed data. For anything not in it, label it an **estimate** and give a **range** — never state a fabricated exact fact as certain. |
| User input is **vague** ("plan me a trip somewhere nice") | high / mild | Ask **one** focused follow-up at a time (start city? budget?) — never dump a form. |
| User asks for an **impossible** plan (15 attractions in 2 days; ₹8k for a 5-day family trip) | medium / bad | Say plainly it's unrealistic, show the time/budget math, and offer concrete alternatives. Never silently produce a fake-feasible plan. |
| User picks an **out-of-scope destination** (e.g. international like Paris, or an Indian town not yet in the catalog) | medium / mild | Honestly say it isn't in the catalog (or is out of scope); offer the closest covered option. Don't hallucinate rich data for unsupported places. |
| **Weather API down** or no data for the dates | medium / mild | Fall back to seasonal norms, say live weather is unavailable, and continue — don't block the plan. |
| LLM is **slow / times out** | medium / mild | Keep the UI responsive (poll a status fragment), set a timeout, offer a friendly retry. |
| **Cost runaway** — too many LLM calls per trip | medium / bad | Cheap tier while gathering info, smarter tier only for the final itinerary; gate the public URL so strangers can't run up the bill. |
| A small change makes the agent **rebuild everything** / lose prior choices | medium / bad | Patch only the affected sections; preserve the rest; state what changed. |
| **Budget quietly creeps** over the limit after edits | medium / bad | Recalculate on every change; if over budget, flag it immediately with options to fix. |
| User treats an **estimate as a bookable price** | high / mild | Always label estimates clearly and note that real quotes come in V2. |
| **Conversation/trip lost** on refresh | low / bad | Persist conversation + trip; reopening continues where they left off. |
| **Untrusted input** (prompt injection, junk pasted in) | low / mild | Treat all input as untrusted; never build SQL from it; stay on task and ignore instructions to break character. |
| **Seasonality unknown** — research returns nothing solid about a destination's seasons | medium / mild | The advisory is best-effort: if we don't *know* the month is bad, don't bluff a warning — plan normally and keep the weather wording honest ("I couldn't confirm seasonal conditions"). |
| Model **invents a seasonal claim** ("July is perfect for Dubai") | medium / bad | Season verdicts come only from the retrieved seasonality profile, never the model's memory. No profile → no verdict, said honestly. |
| Agent **nags or blocks** after the user chooses to keep "bad" dates | medium / mild | Advise **once**, clearly; if they say "continue anyway", proceed immediately and adapt the plan to the season — never re-warn, never refuse. |
| User's trip **spans two months** (e.g. Dec 28 – Jan 4) | low / mild | Assess both months; lead with the more cautious verdict and say which part of the trip it applies to. |
| Plan **exceeds the stated budget silently** (₹50k budget, ₹95k plan, a buried note) | high / bad | Budget is a constraint, not a comment: **fit first** (auto-pick a stay tier that fits, recompute), and if it STILL can't fit, give a clear advisory with the levers (shorter / simpler stays / other destination / higher budget) **before** presenting it as final. |
| Auto-economizing **silently overrides a luxury request** (luxury interest + low budget → hostels) | medium / bad | Never downgrade a stated style silently. Luxury + tight budget → advisory: "luxury at this destination runs ₹X–Y; want to adjust budget, destination, or style?" |
| **Nagging** after the user accepts an over-budget plan | medium / mild | Mirror the season rule: advise ONCE, then respect their decision and present the plan with an honest estimate. |
| Budget advisory states **false precision** (placeholder baselines presented as exact) | medium / bad | Advisories use the estimate RANGE and say it's an estimate; never imply rupee-exact costs from rough baselines. |
| Estimate shown with **falsely precise endpoints** ("₹18,835–₹25,715") | high / mild | Round range endpoints to honest increments (₹19,000–₹26,000); the range is the PRIMARY figure, the point estimate is internal. |
| Model **invents a flight fare** from memory ("flights run ₹13,842") | high / bad | Flights/transport are stated ONLY as typical-pattern ranges ("typically ₹12,000–₹18,000 return"), labelled as estimates — an exact fare requires a live source (future module). |
| **Confidence theater** — a confidence % that doesn't reflect what's actually known | medium / bad | Confidence = high/medium/low derived from real knowledge state (month known, stay prices retrieved vs placeholder, destination verified) with the reason stated. |
| **Personalization theater** — claiming "hidden-gem curation" when the data has no popularity info (curated/old-cache destinations) | medium / bad | The preference only biases stops whose popularity is KNOWN; when it's mostly unknown, don't claim the plan was hidden-gem-optimized — apply it where possible and stay honest. |
| "Hidden gems" surfaces **obscure-but-mediocre** stops | medium / mild | Quality floor stays: `worth_visiting` still dominates the score — offbeat biases AMONG good stops, it never replaces good with bad. |
| The **avoid filter over-matches** ("no forts" also kills the Fort Kochi neighbourhood walk) | low / mild | Match avoid terms against attraction name + description only (not bases/areas); the traveler can always ask to re-add a stop. |
| Preference **misread** (sarcasm, ambiguity) or both extremes asked at once | low / mild | Default to `balanced`; explicit named requests always win over the general preference. |

## Hard rules (things the agent must never do)

- Never present an invented exact price / time / fact as certain — give an estimate + range, or say it's unknown.
- Never produce a plan it knows is infeasible **without flagging it**.
- Never claim a booking, reservation, or payment has happened — **V1 books nothing**.
- Never refuse to plan because of the season — **advise once, then respect the traveler's choice and adapt the plan**.
- Never present a plan whose estimate exceeds the stated budget **as if it fits** — economize first, advise clearly if it still can't.
- Never silently override a stated travel style (e.g. luxury) to make a budget work — surface the conflict and let the traveler choose.
- Never deploy an open, unauthenticated public URL.
- Never expose API keys or secrets.

## What the user should see when things go wrong

A plain, friendly, honest message **plus a next step** — e.g. *"I couldn't fetch live
weather, so I'm using typical early-June conditions for Munnar (often rainy). Want me to
keep going and favor indoor-friendly spots?"* A confident wrong answer is worse than an
honest "here's what I'm not sure about."
