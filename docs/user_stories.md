# User Stories

**Stage 3 — Operationalize success as UX.** (Pair with `failure_modes.md` and `scenarios.md`.)

## Stories

1. As a traveler who already knows my destination, I want to tell TripOS where I'm going, from where, for how long, with whom, and my budget — conversationally — so that I get a tailored plan without filling forms.
2. As a traveler who *doesn't* know where to go, I want to describe my budget, days, and interests and get a few destination suggestions *with reasons*, so that I can choose confidently.
3. As a traveler, I want the agent to ask me a follow-up only when something it needs is missing, so that I don't have to know up front what to tell it.
4. As a traveler with elderly parents, I want the plan to respect limited mobility and a relaxed pace, so that the trip is actually comfortable for them.
5. As a budget-conscious traveler, I want a live, itemized cost estimate I can ask about at any moment ("how much now?"), so that I'm never surprised at the end.
6. As a traveler, I want the agent to flag and refuse unrealistic plans (too many places for the days I have), so that I don't commit to a trip that can't happen.
7. As a traveler, I want to know whether my dates have good weather/season and how crowded it'll be, so that I can adjust timing or expectations.
8. As a traveler, I want every recommendation explained ("why Munnar", "why this attraction"), so that I trust the plan instead of guessing.
9. As a traveler, I want to change the plan by typing naturally ("cheaper stays", "more adventure", "my parents can't walk much") and have *only the relevant parts* update, so that refining is effortless.
10. As a traveler, I want a clean day-by-day final itinerary, so that I can actually follow it on the trip.
11. As a traveler, I want to save my trip and reopen it later, so that I don't lose my work.
12. As a traveler, I want to export my trip as a PDF or a shareable link, so that I can send it to my family and travel companions.
13. As a traveler, I want TripOS to ask *when* I'm travelling and warn me **before planning** if my month is a poor time for that destination (extreme heat, monsoon, cyclones, peak crush), so that I can rethink my timing before I commit.
14. As a traveler with fixed dates (school holidays, leave already approved), I want TripOS to respect my dates after warning me and **adapt the plan to the season** (indoor-leaning, evening-leaning), so that the trip still works as well as it can.
15. As a flexible traveler, I want TripOS to recommend the **best months** for my destination when I'm not sure when to go, so that timing becomes an advantage instead of a guess.
16. As a traveler who knows my exact dates, I want them remembered with my trip, so that booking (when it arrives in a future version) won't have to ask me twice.
17. As a traveler with a fixed budget, I want my per-person budget to **actively shape** the plan — the stays picked, the route suggested — so the estimate lands *within* it instead of surprising me at the end.
18. As a traveler whose trip genuinely can't fit my budget, I want to be told **before** the plan is finalized — with the real options (shorter trip, simpler stays, different destination, higher budget) — so I decide the trade-off, not the planner.
19. As a traveler who asked for **luxury**, I want the planner to tell me when luxury doesn't fit my budget rather than quietly booking me into budget stays, so my stated style is never silently overridden.
20. As a traveler choosing between routes, I want options ranked by how well they fit my budget (best fit first, premium alternatives labelled as such), so popularity never outranks affordability.
21. As a traveler reading the estimate, I want honest **rounded ranges** with a stated **confidence level and its reason** — never a falsely exact ₹48,327 — so I can trust the numbers exactly as far as the planner does.
22. As a traveler, I want every plan to carry a clear **budget feasibility verdict** (fits / slightly above / not realistic) with suggested adjustments, so I always know where I stand without asking.

## What "good" feels like

It feels like texting a sharp, honest friend who happens to be a veteran travel guide:
fast, reassuring, never bureaucratic. The **magic moments** are two — when it *catches*
something I'd have gotten wrong ("that's too much for 2 days with seniors; here's a
saner version"), and when one casual sentence ("make it cheaper") quietly reshapes the
whole trip and re-totals the budget in front of me.

## Out of scope (for now)

- Real hotel / flight / train / bus **booking**, payments, and affiliate links.
- Driver / guide / hotel / restaurant / activity **marketplaces** and partner dashboards (the "send to drivers → quotes → book" flow is **V2**).
- Per-user account logins (V1 sits behind one shared password gate).
- Real-time inventory / live availability.
- Destinations not yet in the catalog (it's data-driven and grows across India); international trips are out of scope.
- A native mobile app.
