"""Tests for the seasonality domain models (models.py).

These guard the contracts the seasonality feature is built on: month lookups, the 1-12
validation, and — important for prod — that enrichments cached BEFORE seasonality existed
still validate (the new fields are all optional).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.tripos.models import (
    MONTH_NAMES,
    GroupType,
    MonthAssessment,
    MonthRating,
    SeasonalityProfile,
    TravelStyle,
    TripBrief,
    TripEnrichment,
)


def _profile() -> SeasonalityProfile:
    return SeasonalityProfile(
        months=[
            MonthAssessment(month=7, rating=MonthRating.not_recommended, note="extreme heat"),
            MonthAssessment(month=12, rating=MonthRating.excellent, note="pleasant winter"),
        ],
        best_months=[11, 12, 1, 2, 3],
        summary="Hot desert summers; mild winters.",
    )


def test_for_month_finds_assessment() -> None:
    assert _profile().for_month(7) is not None
    assessment = _profile().for_month(12)
    assert assessment is not None
    assert assessment.rating is MonthRating.excellent


def test_for_month_returns_none_when_uncovered() -> None:
    assert _profile().for_month(4) is None


def test_month_must_be_1_to_12() -> None:
    with pytest.raises(ValidationError):
        MonthAssessment(month=13, rating=MonthRating.good, note="no such month")
    with pytest.raises(ValidationError):
        TripBrief(
            start_city="Chennai",
            days=3,
            budget=20000,
            group_type=GroupType.couple,
            interests=[TravelStyle.nature],
            travel_month=0,
        )


def test_trip_brief_dates_optional_and_month_none_means_flexible() -> None:
    brief = TripBrief(
        start_city="Chennai",
        days=3,
        budget=20000,
        group_type=GroupType.couple,
        interests=[TravelStyle.nature],
    )
    assert brief.travel_month is None
    assert brief.start_date is None and brief.end_date is None


def test_pre_seasonality_cached_enrichment_still_validates() -> None:
    # Exactly what intelligence_cache holds for destinations enriched before this feature.
    old_json = '{"stays": [], "restaurants": [], "weather": null}'
    enrichment = TripEnrichment.model_validate_json(old_json)
    assert enrichment.seasonality is None


def test_month_names_align_with_numbers() -> None:
    assert MONTH_NAMES[7] == "July"
    assert MONTH_NAMES[12] == "December"
    assert len(MONTH_NAMES) == 13  # index 0 unused
