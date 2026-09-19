"""What the government soil survey says about the nutrients in one area's soil.

This reads the same survey table the fertilizer tool uses (tools/fertilizer/soil_store),
but answers a different question. fertilizer_recommendation collapses the survey into
four numbers and hands them to the dose API; this returns the whole picture — every
macronutrient with its rating, the pH, the salinity, and which micronutrients the area is
short of — so an agent can answer "what is my soil like?" without asking for a dose.

That matters for crop choice as much as for fertilizer. A block where 91% of fields test
low in organic carbon and 90% are boron-deficient is telling the farmer something about
which crops will struggle there, and none of it is visible in a fertilizer quantity.

Everything here describes an *area average* from sampled fields, never the farmer's own
plot. The caveat travels with the data because a survey figure presented as a measurement
invites more confidence than it has earned.
"""

import logging

from strands import tool

from tools.fertilizer import soil_store

logger = logging.getLogger(__name__)

SOURCE = "Soil Health Card nutrient survey, Department of Agriculture & Farmers Welfare"

UNITS = {
    "nitrogen": "kg/ha",
    "phosphorus": "kg/ha",
    "potassium": "kg/ha",
    "organic_carbon": "%",
}

# Report order: the three macros a farmer acts on, then organic carbon, which drives
# water retention and structure rather than a single season's dose.
MACRO_ORDER = ("nitrogen", "phosphorus", "potassium", "organic_carbon")

GRANULARITY_LABEL = {
    "village": "the farmer's village",
    "block": "the farmer's block/taluk",
    "district": "the whole district",
}

# At or above this share of sampled fields, a micronutrient shortage is a property of the
# area rather than of a few plots, and is worth the farmer acting on.
WIDESPREAD_DEFICIENCY_PERCENT = 50


def _macros(row: dict) -> dict:
    macros = row.get("macronutrients") or {}
    result = {}
    for field in MACRO_ORDER:
        entry = macros.get(field)
        if not isinstance(entry, dict):
            continue
        result[field] = {
            "value": entry.get("value"),
            "unit": UNITS[field],
            "level": entry.get("level"),
            "share_of_fields_percent": entry.get("distribution_percent") or {},
        }
    return result


@tool
def soil_type(state: str, district: str = "", block: str = "", village: str = "") -> dict:
    """Get the soil nutrient status of an area from the government soil survey.

    Returns the area's nitrogen, phosphorus, potassium and organic carbon with their
    Soil Health Card ratings, its pH and salinity, and which micronutrients the area is
    deficient in. Use it to describe what the soil is like — for a fertilizer quantity,
    use fertilizer_recommendation instead.

    Give the narrowest location known: a village describes the farmer's own surroundings,
    a district is a wide average across many soils.

    Args:
        state: The farmer's state, e.g. "Karnataka". Required.
        district: The farmer's district. Required in practice — village and block are only
            searched when the district is known, because those names repeat across a state.
        block: The farmer's block or taluk.
        village: The farmer's village, the most representative lookup.
    """
    if not state.strip():
        return {"error": "Specify the farmer's state, e.g. state='Karnataka'."}

    row = soil_store.find(state, district=district, block=block, village=village)
    if not row:
        return {
            "error": f"No soil survey data for the area given in {state.title()}.",
            "next_step": (
                "Ask the farmer for their district, and their village or taluk if they know it. "
                "Without a district this survey cannot be looked up."
            ),
        }

    macros = _macros(row)
    if not macros:
        logger.warning("soil row for %s/%s has no macronutrients", state, district)
        return {"error": f"The soil survey row for this area in {state.title()} has no nutrient data."}

    place = row.get("village") or row.get("block") or row.get("district")
    granularity = row.get("granularity")

    result = {
        "area": place,
        "area_level": granularity,
        "state": (row.get("state") or state).title(),
        "survey_year": row.get("survey_year"),
        "fields_sampled": row.get("samples"),
        "macronutrients": macros,
        "source": SOURCE,
        "caveat": (
            f"These figures are the survey average for {GRANULARITY_LABEL.get(granularity, 'the area')} "
            f"({place}), not a test of this farmer's field. Soil varies field to field — present "
            "them as what the area is typically like, and recommend a Soil Health Card test to confirm."
        ),
    }

    if row.get("soil_ph"):
        result["soil_ph"] = {
            "level": row["soil_ph"].get("level"),
            "share_of_fields_percent": row["soil_ph"].get("distribution_percent") or {},
        }
    if row.get("salinity"):
        result["salinity"] = row["salinity"].get("level")

    deficient = row.get("micronutrient_deficient_percent") or {}
    if deficient:
        ordered = dict(sorted(
            ((name, pct) for name, pct in deficient.items() if isinstance(pct, (int, float))),
            key=lambda kv: kv[1], reverse=True,
        ))
        result["micronutrient_deficient_percent"] = ordered
        widespread = [name for name, pct in ordered.items() if pct >= WIDESPREAD_DEFICIENCY_PERCENT]
        if widespread:
            result["micronutrients_widely_deficient"] = widespread
            result["micronutrient_note"] = (
                f"More than half the fields sampled here are deficient in {', '.join(widespread)}. "
                "That has to be corrected separately — a normal NPK dose does not fix it."
            )

    return result
