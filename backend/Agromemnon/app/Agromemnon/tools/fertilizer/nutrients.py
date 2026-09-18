"""Soil Health Card rating bands, and how a survey distribution becomes a usable number.

The soil-nutrient survey publishes, per village and year, how many sampled fields fell in
each rating band ("Nitrogen Low: 8, Medium: 63, High: 64") rather than any kg/ha figure.
The fertilizer API only accepts numbers, so a distribution has to be collapsed into one.

Snapping to the dominant band throws away too much: a village split 49/51 between Low and
Medium would jump a whole band on one sample. Instead each band contributes its
representative value weighted by its share of samples, so the estimate moves smoothly and
a near-even split lands between the two bands.

The result describes the area, not the farmer's field. Callers must label it that way — an
estimate that reads like a measurement invites more confidence than it has earned.
"""

# (low_below, high_above) — the standard Soil Health Card cut-offs. A value under
# low_below rates Low, over high_above rates High, and between them Medium.
RATING_BANDS = {
    "nitrogen": (280.0, 560.0),
    "phosphorus": (10.0, 25.0),
    "potassium": (108.0, 280.0),
    "organic_carbon": (0.5, 0.75),
}

# The value each band stands in for. Medium is its midpoint; Low and High are open-ended,
# so they use a value typical of Indian survey soils rather than an arbitrary bound.
BAND_VALUES = {
    "nitrogen": {"Low": 200.0, "Medium": 420.0, "High": 700.0},
    "phosphorus": {"Low": 6.0, "Medium": 17.5, "High": 40.0},
    "potassium": {"Low": 70.0, "Medium": 194.0, "High": 400.0},
    "organic_carbon": {"Low": 0.35, "Medium": 0.63, "High": 1.0},
}

# CSV nutrient_name -> our field key. These four are the ones the fertilizer API takes.
MACRO_FIELDS = {
    "Nitrogen": "nitrogen",
    "Phosphorus": "phosphorus",
    "Potassium": "potassium",
    "Organic Carbon": "organic_carbon",
}

MACRO_LEVELS = ("Low", "Medium", "High")

# Reported alongside the macros for context. The fertilizer API takes none of them, but
# they change what a farmer should actually do, so the agent is given them to pass on.
PH_LEVELS = ("Acidic", "Neutral", "Alkaline")
EC_LEVELS = ("Saline", "Non Saline")
MICRO_NUTRIENTS = ("Boron", "Copper", "Iron", "Manganese", "Sulphur", "Zinc")
MICRO_LEVELS = ("Deficient", "Sufficient")


def rate(field: str, value: float) -> str:
    """Rate a numeric nutrient value against its Soil Health Card band."""
    low, high = RATING_BANDS[field]
    if value < low:
        return "low"
    return "medium" if value <= high else "high"


def shares(counts: dict) -> dict:
    """Turn sample counts into percentages of the total, rounded to whole numbers."""
    total = sum(counts.values())
    if not total:
        return {}
    return {level: round(100 * count / total) for level, count in counts.items() if count}


def estimate(field: str, counts: dict):
    """Collapse {"Low": n, "Medium": n, "High": n} into one representative value.

    Returns (value, rating, sample_total), or None when nothing was sampled. The rating is
    the estimate's own band, not the most-sampled one: an area that is 71% Low but close to
    the boundary averages into Medium, and reporting the majority band alongside that value
    would contradict it. The full distribution is reported separately for the spread.
    """
    band_values = BAND_VALUES[field]
    total = sum(counts.get(level, 0) for level in MACRO_LEVELS)
    if not total:
        return None

    weighted = sum(band_values[level] * counts.get(level, 0) for level in MACRO_LEVELS) / total
    precision = 2 if field == "organic_carbon" else 1
    value = round(weighted, precision)
    return value, rate(field, value), total


def dominant(counts: dict, levels) -> str | None:
    """The most-sampled level, or None when nothing was sampled."""
    if not any(counts.get(level, 0) for level in levels):
        return None
    return max(levels, key=lambda level: counts.get(level, 0))
