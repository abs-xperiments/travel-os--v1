"""attraction_selector — choose which stops suit this traveler, and in what order.

A deterministic ranking (no AI, no network): it scores every attraction against the
traveler's interests and group, drops what doesn't suit them, then keeps adding the
best-scoring stops *only while the trip stays feasible* (it asks trip_feasibility_checker).
Finally it orders the kept stops by base and time of day to cut backtracking.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from agent.tripos import trip_feasibility_checker as feasibility
from agent.tripos.models import Attraction, Destination, GroupType, TravelStyle, TripBrief

# When each "best_time" should happen in the day — used only to order stops sensibly.
_TIME_ORDER = {"early morning": 0, "morning": 1, "afternoon": 2, "evening": 3}


def _interest_bonus(attraction: Attraction, interests: list[TravelStyle]) -> float:
    bonus = 0.0
    if TravelStyle.photography in interests:
        bonus += attraction.photography_value * 0.5
    if TravelStyle.adventure in interests:
        bonus += attraction.adventure_level * 0.5
    if TravelStyle.nature in interests and not attraction.indoor:
        bonus += 2.0
    if TravelStyle.relaxation in interests and attraction.adventure_level <= 2:
        bonus += 1.0
    return bonus


def _suits_group(attraction: Attraction, group: GroupType) -> bool:
    """Hard filter: a stop unsuitable for the group is excluded outright, not just penalised.

    Comfort for seniors / children is a core promise, so we never schedule a stop we've
    marked as unsuitable for them — the soft score can't override this.
    """
    too_strenuous_for_seniors = (
        group == GroupType.family_with_seniors and not attraction.suitable_for_seniors
    )
    not_for_children = group == GroupType.family_with_children and not attraction.child_friendly
    return not (too_strenuous_for_seniors or not_for_children)


# Soft seasonal bias, not a hard filter: in a wet/extreme-heat month an indoor stop gets a
# leg-up, but a truly outstanding outdoor stop can still out-score it and be kept.
_INDOOR_SEASON_BONUS = 2.5


def _score(attraction: Attraction, brief: TripBrief, prefer_indoor: bool) -> float:
    """Higher = better fit. Starts from the 'worth visiting' score, adds interest bonuses."""
    score = float(attraction.worth_visiting) + _interest_bonus(attraction, brief.interests)
    if prefer_indoor and attraction.indoor:
        score += _INDOOR_SEASON_BONUS
    return score


def _ordering_key(attraction: Attraction) -> tuple[str, int, int]:
    """Group by base, then early-to-late, then best stops first within a slot."""
    return (
        attraction.base,
        _TIME_ORDER.get(attraction.best_time, 2),
        -attraction.worth_visiting,
    )


def select_attractions(
    destination: Destination, brief: TripBrief, *, prefer_indoor: bool = False
) -> list[Attraction]:
    """Pick the stops that best fit `brief` and still fit in `brief.days`, ordered for flow.

    `prefer_indoor` is the season adaptation: set when the travel month calls for sheltered
    plans (monsoon, extreme heat) so indoor stops out-rank comparable outdoor ones.
    """
    suitable = [a for a in destination.attractions if _suits_group(a, brief.group_type)]
    ranked = sorted(suitable, key=lambda a: _score(a, brief, prefer_indoor), reverse=True)

    chosen: list[Attraction] = []
    for attraction in ranked:
        trial = [*chosen, attraction]
        if feasibility.check_feasibility(trial, brief.days).realistic:
            chosen = trial

    return sorted(chosen, key=_ordering_key)
