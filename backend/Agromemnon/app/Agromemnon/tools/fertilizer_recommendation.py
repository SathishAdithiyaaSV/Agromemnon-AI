import logging

from strands import tool

from tools.fertilizer import nutrients, soil_store, soilhealth

logger = logging.getLogger(__name__)

SOURCE = "Soil Health Card, Department of Agriculture & Farmers Welfare (soilhealth.dac.gov.in)"
SURVEY_SOURCE = "Soil Health Card nutrient survey, aggregated by area"

# Soil test values outside these ranges are a unit mix-up or a typo rather than a real
# reading. The API happily returns a dose for nonsense input, and an absurd dose looks
# just as authoritative as a correct one, so reject it here instead.
VALID_RANGES = {
    "nitrogen": (1.0, 2000.0, "kg/ha"),
    "phosphorus": (0.1, 500.0, "kg/ha"),
    "potassium": (1.0, 2000.0, "kg/ha"),
    "organic_carbon": (0.01, 10.0, "%"),
}

SOIL_FIELDS = ("nitrogen", "phosphorus", "potassium", "organic_carbon")

GRANULARITY_LABEL = {
    "village": "the farmer's village",
    "block": "the farmer's block/taluk",
    "district": "the whole district",
}


def _round(value):
    """Round doses to one decimal — the API returns values like 113.33333333333334."""
    if not isinstance(value, (int, float)):
        return None
    return int(value) if float(value).is_integer() else round(float(value), 1)


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


def _validate(soil_values: dict) -> dict | None:
    """Reject soil values that cannot be a real reading. Returns an error dict or None."""
    for field, value in soil_values.items():
        low, high, unit = VALID_RANGES[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return {"error": f"{field} must be a number from the soil test, in {unit}."}
        if not low <= float(value) <= high:
            return {
                "error": (f"{field} of {value} is outside the plausible range "
                          f"{low}–{high} {unit}; check the units on the soil test."),
                "expected_units": {f: r[2] for f, r in VALID_RANGES.items()},
            }
    return None


def _from_survey(state: str, district: str, block: str, village: str):
    """Look up area-typical soil values from the survey table.

    Returns (soil_values, provenance) or None when the area was never surveyed.
    """
    row = soil_store.find(state, district=district, block=block, village=village)
    if not row:
        return None

    macros = row.get("macronutrients") or {}
    if any(field not in macros for field in SOIL_FIELDS):
        return None

    soil_values = {field: macros[field]["value"] for field in SOIL_FIELDS}

    place = row.get("village") or row.get("block") or row.get("district")
    provenance = {
        "basis": "area_survey",
        "area": place,
        "area_level": row.get("granularity"),
        "survey_year": row.get("survey_year"),
        "fields_sampled": row.get("samples"),
        "nutrient_levels": {field: macros[field]["level"] for field in SOIL_FIELDS},
        "level_distribution_percent": {
            field: macros[field].get("distribution_percent") or {} for field in SOIL_FIELDS
        },
        "source": SURVEY_SOURCE,
        "caveat": (
            f"These values are the survey average for {GRANULARITY_LABEL.get(row.get('granularity'), 'the area')} "
            f"({place}), not a test of this farmer's field. Soil varies field to field, so "
            "present the dose as a starting point and recommend a Soil Health Card test to confirm it."
        ),
    }

    # Context the fertilizer API does not accept but that changes what the farmer should do.
    if row.get("soil_ph"):
        provenance["soil_ph"] = row["soil_ph"].get("level")
    if row.get("salinity"):
        provenance["salinity"] = row["salinity"].get("level")
    deficient = row.get("micronutrient_deficient_percent") or {}
    # Below roughly half the sampled fields, a deficiency is not the area's defining problem
    # and listing it alongside the severe ones would flatten the difference.
    short = {name: pct for name, pct in deficient.items() if isinstance(pct, (int, float)) and pct >= 50}
    if short:
        provenance["micronutrients_widely_deficient_percent"] = dict(
            sorted(short.items(), key=lambda kv: kv[1], reverse=True))

    return soil_values, provenance


@tool
def fertilizer_recommendation(crop: str, state: str, district: str = "", block: str = "",
                              village: str = "", nitrogen: float | None = None,
                              phosphorus: float | None = None, potassium: float | None = None,
                              organic_carbon: float | None = None, season: str = "",
                              irrigation: str = "") -> dict:
    """Get the government fertilizer dose recommended for a crop in a particular place.

    Soil test values are optional. When they are omitted the tool infers the area's typical
    soil condition from the government soil-nutrient survey, so a farmer who has never had
    their soil tested still gets a recommendation. Give the narrowest location known — a
    village is far more representative than a whole district.

    Pass the soil test values only if the farmer actually has a Soil Health Card in hand;
    they override the survey and make the dose specific to their field. Never invent them.

    Returns fertilizer combinations and organic manure options, all per hectare, along with
    which soil values were used and where they came from.

    Args:
        crop: Crop name in English, e.g. "banana", "paddy", "arecanut".
        state: The farmer's state, e.g. "Karnataka". Required — recommendations are published per state.
        district: The farmer's district. Strongly recommended; needed to use the soil survey.
        block: The farmer's block or taluk, which narrows the soil survey lookup.
        village: The farmer's village, the most representative soil survey lookup.
        nitrogen: Optional measured available nitrogen (N) in kg/ha, from a soil test.
        phosphorus: Optional measured available phosphorus (P) in kg/ha, from a soil test.
        potassium: Optional measured available potassium (K) in kg/ha, from a soil test.
        organic_carbon: Optional measured organic carbon (OC) as a percentage, from a soil test.
        season: Optional season to pick a crop variant — "Kharif" or "Rabi".
        irrigation: Optional irrigation type to pick a crop variant — "Irrigated" or "Rainfed".
    """
    if not crop.strip():
        return {"error": "Specify which crop to fertilize, e.g. crop='banana', state='Karnataka'."}
    if not state.strip():
        return {"error": "Specify the farmer's state — recommendations are published per state."}

    measured = {"nitrogen": nitrogen, "phosphorus": phosphorus,
                "potassium": potassium, "organic_carbon": organic_carbon}
    supplied = {field: value for field, value in measured.items() if value is not None}

    # A half-filled soil test is more likely a transcription slip than a real reading, and
    # silently topping it up from the survey would hide which numbers came from where.
    if supplied and len(supplied) != len(SOIL_FIELDS):
        return {
            "error": ("Give all four soil test values or none: "
                      f"missing {sorted(set(SOIL_FIELDS) - set(supplied))}. "
                      "Omit them all to use the area's soil survey instead."),
        }

    if supplied:
        invalid = _validate(supplied)
        if invalid:
            return invalid
        soil_values = supplied
        provenance = {
            "basis": "farmer_soil_test",
            "source": "Soil test values supplied by the farmer.",
        }
    else:
        found_soil = _from_survey(state, district, block, village)
        if found_soil is None:
            return {
                "error": (f"No soil survey data for the area given in {state.title()}, and no soil "
                          "test values were supplied."),
                "next_step": ("Ask the farmer for their district (and village or taluk if they know it), "
                              "or for the N, P, K and organic carbon figures on their Soil Health Card."),
            }
        soil_values, provenance = found_soil
        invalid = _validate(soil_values)
        if invalid:
            logger.warning("survey-derived soil values rejected for %s/%s: %s",
                           state, district, invalid["error"])
            return {"error": "The soil survey data for this area looks implausible; "
                             "ask the farmer for their Soil Health Card values instead."}

    try:
        found = soilhealth.recommend(
            crop=crop,
            state=state,
            soil={"n": str(soil_values["nitrogen"]), "p": str(soil_values["phosphorus"]),
                  "k": str(soil_values["potassium"]), "OC": str(soil_values["organic_carbon"])},
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
        "soil_values_used": {
            "nitrogen_kg_per_ha": soil_values["nitrogen"],
            "phosphorus_kg_per_ha": soil_values["phosphorus"],
            "potassium_kg_per_ha": soil_values["potassium"],
            "organic_carbon_percent": soil_values["organic_carbon"],
        },
        "soil_ratings": {field: nutrients.rate(field, float(value))
                         for field, value in soil_values.items()},
        "soil_data_provenance": provenance,
        "recommendations": [],
        "dose_basis": "Quantities are per hectare for the whole crop season.",
        "source": SOURCE,
    }
    if found["district"]:
        result["district"] = found["district"].title()

    # Paired on the API's own label, not by position: see soilhealth.pair_recommendations.
    for variant, recommendation in soilhealth.pair_recommendations(
            found["variants"], found["recommendations"]):
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
