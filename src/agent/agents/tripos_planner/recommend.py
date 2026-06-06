"""Standalone stay & restaurant recommendations — the FIND_STAYS / FIND_RESTAURANTS tools.

Not every traveler wants a trip planned: "suggest homestays in Didupe under ₹10,000" is an
accommodation request, full stop. These tools serve that intent directly — no itinerary
questions — by reusing the SAME cached destination enrichment the trip builder uses (so a
stays answer today makes a full plan for the same place a cache hit), ranking the results
against what the traveler actually asked (kind, budget, area, cuisine, occasion), and
answering honestly when little matches (never inventing places).

The ranking helpers are pure functions — tested offline in test_recommendations.py.
"""

from __future__ import annotations

from agent.tripos import destination_suggestion, trip_intelligence
from agent.tripos.models import (
    Accommodation,
    DestinationIdea,
    FoodPref,
    GroupType,
    Restaurant,
    TravelStyle,
    TripBrief,
)
from agent.tripos.provider_interfaces import slugify
from agent.tripos.providers import web_intelligence

from . import progress
from .tools import rank_circuits_by_budget


def _normalize(word: str) -> str:
    """Lowercase + singular-ish, so "Homestays" matches kind="homestay" (plural learning,
    journal 2026-06-06: 'no forts' must catch 'Amber Fort')."""
    w = word.strip().casefold()
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def _mid_price(s: Accommodation) -> float:
    return (s.price_per_night_low + s.price_per_night_high) / 2


def _matches_kind(stay: Accommodation, kind: str) -> bool:
    k, sk = _normalize(kind), _normalize(stay.kind)
    return k in sk or sk in k


def _rank_stays(
    stays: list[Accommodation],
    budget_per_night: float | None = None,
    kind: str | None = None,
    area: str | None = None,
) -> tuple[list[Accommodation], str | None]:
    """Rank stays against the ask. Returns (ranked, honest_note_or_None).

    Affordability is never outranked by anything (mirrors rank_circuits_by_budget): stays that
    fit the nightly budget lead, best-rated first; the rest follow cheapest-first. Filters are
    honest, not silent — when nothing matches the kind or budget, we say so in the note and
    show the closest real options instead of an empty (or invented) list.
    """
    pool, notes = list(stays), []

    if kind:
        matched = [s for s in pool if _matches_kind(s, kind)]
        if matched:
            pool = matched
        else:
            notes.append(f"No {kind} options surfaced here — these are the closest stays.")

    if area:  # soft filter: only narrow when something actually matches the area
        a = area.casefold()
        matched = [s for s in pool if a in s.area.casefold()]
        if matched:
            pool = matched

    if budget_per_night and budget_per_night > 0:
        fits = [s for s in pool if s.price_per_night_high <= budget_per_night]
        rest = [s for s in pool if s not in fits]
        if not fits:
            notes.append(
                f"Nothing came in under ₹{budget_per_night:,.0f}/night — "
                "these are the closest-priced real options."
            )
            ranked = sorted(pool, key=_mid_price)  # cheapest first, honestly over budget
        else:
            ranked = sorted(fits, key=lambda s: (-(s.rating or 0), _mid_price(s))) + sorted(
                rest, key=_mid_price
            )
    else:
        ranked = sorted(pool, key=lambda s: (-(s.rating or 0), _mid_price(s)))

    return ranked, (" ".join(notes) or None)


def _stay_tradeoff(s: Accommodation, pick: Accommodation) -> str | None:
    """A factual one-line tradeoff vs the recommended pick — derived from data, never invented."""
    if s is pick:
        return None
    bits: list[str] = []
    if _mid_price(s) > _mid_price(pick):
        bits.append("pricier than the top pick")
    elif _mid_price(s) < _mid_price(pick):
        bits.append("cheaper than the top pick")
    if s.area and pick.area and s.area.casefold() != pick.area.casefold():
        bits.append(f"in {s.area} rather than {pick.area}")
    if s.rating is not None and pick.rating is not None and s.rating < pick.rating:
        bits.append("rated a touch lower")
    return ", ".join(bits) or None


def _stay_view(s: Accommodation, pick: Accommodation, ceiling: float | None) -> dict:
    return {
        "name": s.name,
        "area": s.area,
        "kind": s.kind,
        "tier": s.tier,
        "price_per_night": [s.price_per_night_low, s.price_per_night_high],  # ₹, estimate
        "rating": s.rating,
        "fits_budget": (s.price_per_night_high <= ceiling) if ceiling else None,
        "why": s.why,
        "tradeoffs": _stay_tradeoff(s, pick),
    }


async def find_stays(
    destination: str,
    budget_per_night: float | None = None,
    total_budget: float | None = None,
    nights: int | None = None,
    group_type: str = "couple",
    kind: str | None = None,
    area: str | None = None,
) -> dict:
    """Recommend places to STAY in a destination — a top pick + ranked alternatives.

    Use this for a standalone accommodation request ("suggest homestays in Didupe under
    ₹10,000") — it does NOT plan a trip and you must NOT ask itinerary questions around it.
    Returns a recommended stay + alternatives with ₹/night ranges (estimates, never live
    quotes), why each is good, review quality when known, and honest tradeoffs — or an `error`
    to relay.

    - budget_per_night: the ROOM price per night they're willing to pay (₹). If they gave a
      TOTAL accommodation budget instead, pass total_budget (+ nights when known) and it's
      converted.
    - kind: the stay type they asked for — "homestay", "resort", "hostel", "boutique"…
    - area: a neighbourhood/locality they mentioned.
    - group_type: solo, couple, friends, family, family_with_children, family_with_seniors.
    """
    try:
        group = GroupType(group_type)
    except ValueError as exc:
        return {"error": f"Invalid input: {exc}"}
    if budget_per_night is not None and budget_per_night <= 0:
        return {"error": "budget_per_night must be positive"}
    if total_budget is not None and total_budget <= 0:
        return {"error": "total_budget must be positive"}
    if nights is not None and nights <= 0:
        return {"error": "nights must be positive"}

    ceiling = budget_per_night or (total_budget / nights if total_budget and nights else None)
    # The brief only colours the first extraction (variety) — budget here is a stand-in.
    brief = TripBrief(
        start_city="(unspecified)",
        days=nights or 3,
        budget=total_budget or (ceiling * (nights or 3) if ceiling else 50000),
        group_type=group,
        interests=[TravelStyle.sightseeing],
    )
    progress.step(f"Scanning stays in {destination}")
    enrichment = await trip_intelligence.enrich_by_name(destination, brief)
    stays = enrichment.stays

    # Thin-result fallback: the generic enrichment fetches 2–3 stays per TIER, which can miss a
    # specific ask ("homestays" in a tiny village). One focused retrieval, cached under its own
    # key so it never overwrites the canonical enrichment the trip builder relies on.
    if not stays or (kind and len([s for s in stays if _matches_kind(s, kind)]) < 2):
        # The extra wait gets an honest reason on the checklist.
        progress.step(f"Digging deeper for {kind or 'stay'} options")
        focus = f"the best {kind or 'places to stay'} options across price ranges"
        key = f"{slugify(destination)}:stays:{_normalize(kind) if kind else 'any'}:v1"
        focused = await web_intelligence.gather_focused(destination, focus, key)
        seen = {s.name.casefold() for s in focused.stays}
        stays = focused.stays + [s for s in stays if s.name.casefold() not in seen]

    progress.step("Ranking what fits your ask")
    ranked, note = _rank_stays(stays, ceiling, kind, area)
    progress.complete()
    if not ranked:
        return {
            "error": f"I couldn't find stays I can vouch for in {destination!r}. "
            "Could you check the spelling, or name a nearby well-known town?"
        }

    pick = ranked[0]
    return {
        "destination": destination,
        "ask": {
            "kind": kind,
            "budget_per_night": ceiling,
            "area": area,
            "group": group.value,
        },
        "currency": "INR",
        "recommended": _stay_view(pick, pick, ceiling),
        "alternatives": [_stay_view(s, pick, ceiling) for s in ranked[1:4]],
        "no_match_note": note,
        "notes": ["Prices are web-sourced estimates, not live quotes."],
    }


def _matches_text(r: Restaurant, term: str) -> bool:
    t = _normalize(term)
    return t in _normalize(r.cuisine) or t in r.good_for.casefold() or t in r.why.casefold()


def _veg_friendly(r: Restaurant) -> bool:
    """True for genuinely veg-friendly spots — "non-veg" must NOT match by substring (the
    same trap as "no forts" missing "Amber Fort", just inverted)."""
    text = (r.good_for + " " + r.why).casefold()
    for negation in ("non-veg", "non veg", "nonveg"):
        text = text.replace(negation, "")
    return "veg" in text


def _rank_restaurants(
    restaurants: list[Restaurant],
    cuisine: str | None = None,
    food_pref: FoodPref = FoodPref.no_preference,
    occasion: str | None = None,
    area: str | None = None,
    price_band: str | None = None,
) -> tuple[list[Restaurant], str | None]:
    """Rank restaurants against the ask. Returns (ranked, honest_note_or_None).

    Cuisine is the strongest signal; the rest are soft preferences (matches lead, nothing is
    silently dropped). When no spot matches the cuisine, we say so honestly instead of
    pretending the generic list is what they asked for.
    """
    pool, note = list(restaurants), None

    if cuisine:
        matched = [r for r in pool if _matches_text(r, cuisine)]
        if matched:
            pool = matched
        else:
            note = f"No clear {cuisine} spots surfaced — these are the best alternatives nearby."

    if price_band:  # soft: prefer the asked band, keep the rest behind it
        pool = [r for r in pool if r.price_band == price_band] + [
            r for r in pool if r.price_band != price_band
        ]
    if area:
        a = area.casefold()
        pool = [r for r in pool if a in r.area.casefold()] + [
            r for r in pool if a not in r.area.casefold()
        ]
    if food_pref in (FoodPref.vegetarian, FoodPref.vegan, FoodPref.jain):
        pool = [r for r in pool if _veg_friendly(r)] + [r for r in pool if not _veg_friendly(r)]
    if occasion:
        o = _normalize(occasion)
        pool = [r for r in pool if o in (r.good_for + r.why).casefold()] + [
            r for r in pool if o not in (r.good_for + r.why).casefold()
        ]

    return pool, note


def _restaurant_view(r: Restaurant) -> dict:
    return {
        "name": r.name,
        "area": r.area,
        "cuisine": r.cuisine,
        "price_band": r.price_band,
        "good_for": r.good_for,
        "why": r.why,
    }


async def find_restaurants(
    destination: str,
    cuisine: str | None = None,
    food_pref: str = "no_preference",
    occasion: str | None = None,
    area: str | None = None,
    price_band: str | None = None,
) -> dict:
    """Recommend places to EAT in a destination — a top pick + ranked alternatives.

    Use this for a standalone food request ("best seafood restaurants in Kochi") — it does NOT
    plan a trip and you must NOT ask itinerary questions around it. Returns a recommended spot
    + alternatives with cuisine, price band, what each is good for, and why — or an `error`.

    - cuisine: what they asked for ("seafood", "South Indian", "street food"…).
    - food_pref: vegetarian | non_vegetarian | jain | vegan | no_preference.
    - occasion: "romantic dinner", "family lunch", "quick bite"… (soft preference).
    - price_band: "$" | "$$" | "$$$" if they signalled a level.
    """
    try:
        pref = FoodPref(food_pref)
    except ValueError as exc:
        return {"error": f"Invalid input: {exc}"}
    if price_band is not None and price_band not in ("$", "$$", "$$$"):
        return {"error": "price_band must be one of $, $$, $$$"}

    brief = TripBrief(
        start_city="(unspecified)",
        days=3,
        budget=50000,
        group_type=GroupType.couple,
        interests=[TravelStyle.food],
        food_pref=pref,
    )
    progress.step(f"Scanning places to eat in {destination}")
    enrichment = await trip_intelligence.enrich_by_name(destination, brief)
    restaurants = enrichment.restaurants

    # Thin-result fallback, same pattern (and the same caveats) as find_stays.
    if not restaurants or (
        cuisine and len([r for r in restaurants if _matches_text(r, cuisine)]) < 2
    ):
        progress.step(f"Digging deeper for {cuisine or 'food'} spots")
        focus = f"the best {cuisine or 'restaurants and local food'} places to eat"
        key = f"{slugify(destination)}:food:{_normalize(cuisine) if cuisine else 'any'}:v1"
        focused = await web_intelligence.gather_focused(destination, focus, key)
        seen = {r.name.casefold() for r in focused.restaurants}
        restaurants = focused.restaurants + [
            r for r in restaurants if r.name.casefold() not in seen
        ]

    progress.step("Ranking what fits your ask")
    ranked, note = _rank_restaurants(restaurants, cuisine, pref, occasion, area, price_band)
    progress.complete()
    if not ranked:
        return {
            "error": f"I couldn't find restaurants I can vouch for in {destination!r}. "
            "Could you check the spelling, or name a nearby well-known town?"
        }

    return {
        "destination": destination,
        "ask": {
            "cuisine": cuisine,
            "food_pref": pref.value,
            "occasion": occasion,
            "area": area,
            "price_band": price_band,
        },
        "recommended": _restaurant_view(ranked[0]),
        "alternatives": [_restaurant_view(r) for r in ranked[1:4]],
        "no_match_note": note,
        "notes": ["Estimates from recent reviews — worth confirming hours before going."],
    }


def _idea_view(idea: DestinationIdea, budget_fit: str | None) -> dict:
    return {
        "name": idea.name,
        "country": idea.country,
        "why": idea.why,
        "best_season": idea.best_season,
        "est_per_person_budget": idea.est_per_person_budget,  # rough ₹, estimate
        "budget_fit": budget_fit,  # fits | stretch | premium | unknown (None = no budget given)
        "good_for": idea.good_for,
        "tradeoffs": idea.tradeoffs,
    }


async def suggest_destinations(
    days: int | None = None,
    month: int | None = None,
    budget: float | None = None,
    interests: list[str] | None = None,
    region: str | None = None,
    start_city: str | None = None,
) -> dict:
    """Suggest WHERE to go — 3–5 ranked destination ideas for the traveler's constraints.

    Use this when they want destination IDEAS ("where should I go for 5 days in December?",
    "beach ideas under ₹40k") — NOT a route through a known region (that's discover_circuits)
    and NOT a full plan (that's build_trip, after they pick). Pass whatever they gave; nothing
    here is required. Returns ideas ranked best-budget-fit first, each with why, season fit,
    a rough per-person budget, and an honest tradeoff — or an `error`.

    - month: 1–12 (resolve "this December" etc. from the travel context first).
    - budget: PER-PERSON, in ₹.
    - interests: nature, adventure, food, relaxation, photography, road_trip, backpacking,
      luxury, sightseeing.
    """
    if month is not None and not 1 <= month <= 12:
        return {"error": "month must be 1-12"}
    if days is not None and days <= 0:
        return {"error": "days must be positive"}
    if budget is not None and budget <= 0:
        return {"error": "budget must be positive"}
    if interests:
        try:
            interests = [TravelStyle(i).value for i in interests]
        except ValueError as exc:
            return {"error": f"Invalid input: {exc}"}

    ideas = await destination_suggestion.suggest(
        days=days,
        month=month,
        budget=budget,
        interests=interests,
        region=region,
        start_city=start_city,
    )
    if not ideas:
        return {
            "error": "I couldn't put together destination ideas for that just now. "
            "Want to tell me a region you're drawn to, or shall I suggest classics?"
        }

    if budget:
        # Best budget fit leads — same rule as circuits: fame never outranks affordability.
        ranked = rank_circuits_by_budget(ideas, budget)
        views = [_idea_view(idea, label) for idea, label in ranked]
    else:
        views = [_idea_view(idea, None) for idea in ideas]

    return {
        "constraints": {
            "days": days,
            "month": month,
            "budget": budget,
            "interests": interests or [],
            "region": region,
            "start_city": start_city,
        },
        "currency": "INR",
        "recommended": views[0],
        "alternatives": views[1:5],
        "notes": [
            "Budgets are rough estimates; the season fit is confirmed in detail once a "
            "destination is chosen."
        ],
    }
