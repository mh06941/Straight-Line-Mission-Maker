"""Planned-route grades use the unrounded maximum deviation in canonical metres.

These are planning estimates from modelled geometry, not grades of a completed
traveler track. Access confidence and route feasibility remain separate.
"""

import math

RULES = (
    {"tier": "diamond", "label": "Diamond", "cutoff_m": 10, "inclusive": False, "range": "Under 10 m"},
    {
        "tier": "platinum",
        "label": "Platinum",
        "cutoff_m": 25,
        "inclusive": False,
        "range": "10 to under 25 m",
    },
    {"tier": "gold", "label": "Gold", "cutoff_m": 50, "inclusive": False, "range": "25 to under 50 m"},
    {"tier": "silver", "label": "Silver", "cutoff_m": 75, "inclusive": False, "range": "50 to under 75 m"},
    {
        "tier": "bronze",
        "label": "Bronze",
        "cutoff_m": 100,
        "inclusive": True,
        "range": "75 to 100 m inclusive",
    },
    {
        "tier": "out_of_grade",
        "label": "Out of grade",
        "cutoff_m": None,
        "inclusive": False,
        "range": "Over 100 m",
    },
)


def grade_deviation(max_deviation_m):
    if max_deviation_m is None:
        return None
    if not math.isfinite(max_deviation_m) or max_deviation_m < 0:
        raise ValueError("Maximum deviation must be a finite nonnegative distance.")
    for rule in RULES:
        cutoff = rule["cutoff_m"]
        if cutoff is None or max_deviation_m < cutoff or (rule["inclusive"] and max_deviation_m == cutoff):
            return {**rule, "max_deviation_m": max_deviation_m}
    raise AssertionError("Grading scale must include an open-ended final tier.")
