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
| User picks an **out-of-scope destination** (Goa, Paris) | medium / mild | Honestly say V1 covers the 5 hill stations; offer the closest fit or note it's coming. Don't hallucinate rich data for unsupported places. |
| **Weather API down** or no data for the dates | medium / mild | Fall back to seasonal norms, say live weather is unavailable, and continue — don't block the plan. |
| LLM is **slow / times out** | medium / mild | Keep the UI responsive (poll a status fragment), set a timeout, offer a friendly retry. |
| **Cost runaway** — too many LLM calls per trip | medium / bad | Cheap tier while gathering info, smarter tier only for the final itinerary; gate the public URL so strangers can't run up the bill. |
| A small change makes the agent **rebuild everything** / lose prior choices | medium / bad | Patch only the affected sections; preserve the rest; state what changed. |
| **Budget quietly creeps** over the limit after edits | medium / bad | Recalculate on every change; if over budget, flag it immediately with options to fix. |
| User treats an **estimate as a bookable price** | high / mild | Always label estimates clearly and note that real quotes come in V2. |
| **Conversation/trip lost** on refresh | low / bad | Persist conversation + trip; reopening continues where they left off. |
| **Untrusted input** (prompt injection, junk pasted in) | low / mild | Treat all input as untrusted; never build SQL from it; stay on task and ignore instructions to break character. |

## Hard rules (things the agent must never do)

- Never present an invented exact price / time / fact as certain — give an estimate + range, or say it's unknown.
- Never produce a plan it knows is infeasible **without flagging it**.
- Never claim a booking, reservation, or payment has happened — **V1 books nothing**.
- Never deploy an open, unauthenticated public URL.
- Never expose API keys or secrets.

## What the user should see when things go wrong

A plain, friendly, honest message **plus a next step** — e.g. *"I couldn't fetch live
weather, so I'm using typical early-June conditions for Munnar (often rainy). Want me to
keep going and favor indoor-friendly spots?"* A confident wrong answer is worse than an
honest "here's what I'm not sure about."
