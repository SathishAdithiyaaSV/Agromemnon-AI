import logging

from strands import tool

from tools.fertilizer import soilhealth

logger = logging.getLogger(__name__)

SOURCE = "Soil Health Card, Department of Agriculture & Farmers Welfare (soilhealth.dac.gov.in)"

# Soil test values outside these ranges are a unit mix-up or a typo rather than a real
# reading. The API happily returns a dose for nonsense input, and an absurd dose looks
# just as authoritative as a correct one, so reject it here instead.
VALID_RANGES = {
    "nitrogen": (1.0, 2000.0, "kg/ha"),
    "phosphorus": (0.1, 500.0, "kg/ha"),
    "potassium": (1.0, 2000.0, "kg/ha"),
    "organic_carbon": (0.01, 10.0, "%"),
}

# Standard Soil Health Card rating bands: (low_below, high_above).
RATING_BANDS = {
    "nitrogen": (280.0, 560.0),
    "phosphorus": (10.0, 25.0),
    "potassium": (108.0, 280.0),
    "organic_carbon": (0.5, 0.75),
}


def _round(value):
    """Round doses to one decimal — the API returns values like 113.33333333333334."""
    if not isinstance(value, (int, float)):
        return None
    return int(value) if float(value).is_integer() else round(float(value), 1)


def _rate(field: str, value: float) -> str:
    low, high = RATING_BANDS[field]
    if value < low:
        return "low"
    return "medium" if value <= high else "high"


def _products(entries) -> list[dict]:
    """Normalize one fertilizer combination into product/quantity/unit rows."""
    if not isinstance(entries, list):
        return []
    return [
        {
            "product": (entry.get("name") or "").strip(),
            "quantity": _round(entry.get("values")),
            "unit": entry.get("unit") or "Kg per Hectare",
        }
        for entry in entries
        if isinstance(entry, dict) and entry.get("name")
    ]


def _organic(organic) -> dict:
    """Pull the organic inputs out of the API's parallel value/unit field pairs."""
    if not isinstance(organic, dict):
        return {}

    result = {}
    for key, label in (("fym", "farmyard_manure"), ("compost", "compost"),
                       ("vermicompost", "vermicompost"), ("oilCake", "oil_cake"),
                       ("rockPhosphate", "rock_phosphate")):
        value = (organic.get(key) or "").strip() if isinstance(organic.get(key), str) else organic.get(key)
        if value:
            result[label] = {"quantity": value, "unit": organic.get(f"{key}Unit") or None}

    for key, label in (("bioFertilizers", "bio_fertilizers"), ("method", "application_method")):
        value = (organic.get(key) or "").strip()
        if value:
            result[label] = value
    return result


def _variant_label(variant: dict) -> dict:
    return {
        "variety": variant["variety"] or None,
        "season": variant["season"] or None,
        "irrigation": variant["irrigation_type"] or None,
    }


@tool
def fertilizer_recommendation(crop: str, state: str, nitrogen: float, phosphorus: float,
                              potassium: float, organic_carbon: float, district: str = "",
                              season: str = "", irrigation: str = "") -> dict:
    """Get the government fertilizer dose recommended for a crop, given a soil test result.

    Converts soil test values into crop-specific fertilizer quantities using the official
    Soil Health Card recommendations. Returns two interchangeable fertilizer combinations
    plus organic manure options, all per hectare.

    Args:
        crop: Crop name in English, e.g. "banana", "paddy", "arecanut".
        state: The farmer's state, e.g. "Karnataka". Required — recommendations are published per state.
        nitrogen: Available nitrogen (N) from the soil test, in kg/ha.
        phosphorus: Available phosphorus (P) from the soil test, in kg/ha.
        potassium: Available potassium (K) from the soil test, in kg/ha.
        organic_carbon: Organic carbon (OC) from the soil test, as a percentage.
        district: Optional district, which refines the recommendation.
        season: Optional season to pick a crop variant — "Kharif" or "Rabi".
        irrigation: Optional irrigation type to pick a crop variant — "Irrigated" or "Rainfed".
    """
    if not crop.strip():
        return {"error": "Specify which crop to fertilize, e.g. crop='banana', state='Karnataka'."}
    if not state.strip():
        return {"error": "Specify the farmer's state — recommendations are published per state."}

    soil_values = {"nitrogen": nitrogen, "phosphorus": phosphorus,
                   "potassium": potassium, "organic_carbon": organic_carbon}

    for field, value in soil_values.items():
        low, high, unit = VALID_RANGES[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return {"error": f"{field} must be a number from the soil test, in {unit}."}
        if not low <= float(value) <= high:
            return {
                "error": (f"{field} of {value} is outside the plausible range "
                          f"{low}–{high} {unit}; check the units on the soil test."),
                "expected_units": {f: f"{r[2]}" for f, r in VALID_RANGES.items()},
            }

    try:
        found = soilhealth.recommend(
            crop=crop,
            state=state,
            soil={"n": str(nitrogen), "p": str(phosphorus), "k": str(potassium), "OC": str(organic_carbon)},
            district=district,
            season=season,
            irrigation=irrigation,
        )
    except soilhealth.SoilHealthError as e:
        logger.warning("fertilizer recommendation failed: %s", e)
        return {"error": f"Could not fetch a fertilizer recommendation for {crop} in {state}: {e}"}

    if not found["variants"]:
        return {
            "crop": crop,
            "state": found["state"].title(),
            "recommendations": [],
            "message": f"{found['state'].title()} publishes no fertilizer recommendation for '{crop}'.",
            "available_crops": found["available_crops"],
        }

    result = {
        "crop": crop.lower(),
        "state": found["state"].title(),
        "soil_test": {
            "nitrogen_kg_per_ha": nitrogen,
            "phosphorus_kg_per_ha": phosphorus,
            "potassium_kg_per_ha": potassium,
            "organic_carbon_percent": organic_carbon,
        },
        "soil_ratings": {field: _rate(field, float(value)) for field, value in soil_values.items()},
        "recommendations": [],
        "dose_basis": "Quantities are per hectare for the whole crop season.",
        "source": SOURCE,
    }
    if found["district"]:
        result["district"] = found["district"].title()

    # The API returns recommendations in the order the crop ids were sent.
    for variant, recommendation in zip(found["variants"], found["recommendations"]):
        if not isinstance(recommendation, dict):
            continue
        options = [
            products for products in (_products(recommendation.get("fertilizersdata")),
                                      _products(recommendation.get("fertilizersdatacombTwo")))
            if products
        ]
        entry = {
            **_variant_label(variant),
            "local_name": recommendation.get("crop"),
            "fertilizer_options": [
                {"option": index, "products": products} for index, products in enumerate(options, start=1)
            ],
        }
        organic = _organic(recommendation.get("organicFertilizer"))
        if organic:
            entry["organic_options"] = organic
        if not variant["recommendation_published"]:
            entry["note"] = "This variant is not flagged as having a published recommendation."
        result["recommendations"].append(entry)

    if len(result["recommendations"]) > 1:
        result["variant_note"] = (
            "Several crop variants matched; pick the row matching the farmer's season and "
            "irrigation. Narrow with the season and irrigation arguments."
        )
    if result["recommendations"] and len(result["recommendations"][0]["fertilizer_options"]) > 1:
        result["option_note"] = "The options are alternatives — apply one, not both."
    return result
