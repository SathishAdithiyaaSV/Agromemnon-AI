"""Soil Health Card fertilizer recommendation source.

The government Soil Health Card portal (soilhealth.dac.gov.in) exposes a GraphQL API
that turns a soil test result into crop-specific fertilizer doses — the same numbers
printed on a farmer's Soil Health Card. Three queries are needed:

  getProgressReportForPortal  state and district ids (there is no location query;
                              this report endpoint is the only public id source)
  getCropRegistries           the crops a state publishes recommendations for
  getRecommendations          the doses, given soil values, state, district and crops

Ids are Mongo ObjectIds that must be resolved by name on every call.
"""

import logging

import requests

from tools.matching import best_match, normalize, resolve_name

logger = logging.getLogger(__name__)

# The GraphQL router answers on any path; /graphql is the conventional one.
ENDPOINT = "https://soilhealth4.dac.gov.in/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Referer": "https://soilhealth.dac.gov.in/",
}

TIMEOUT = 60
# Asking for every matching crop variant at once costs one request, but a farmer does
# not need a dozen near-identical dose tables.
MAX_VARIANTS = 4

PROGRESS_REPORT_QUERY = """
query GetProgressReportForPortal($state: ID) {
  getProgressReportForPortal(state: $state)
}
"""

CROP_REGISTRIES_QUERY = """
query GetCropRegistries($state: String) {
  getCropRegistries(state: $state) {
    id
    name
    variety
    season
    irrigationType
    GFRavailable
  }
}
"""

RECOMMENDATIONS_QUERY = """
query GetRecommendations($state: ID!, $results: JSON!, $district: ID, $crops: [ID!]) {
  getRecommendations(state: $state, results: $results, district: $district, crops: $crops)
}
"""


class SoilHealthError(Exception):
    """Raised when the Soil Health Card API cannot be reached or returns nothing usable."""


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _query(session: requests.Session, query: str, variables: dict, field: str):
    """Run one GraphQL query and return the named data field."""
    response = session.post(ENDPOINT, json={"query": query, "variables": variables}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    if payload.get("errors"):
        messages = "; ".join(e.get("message", "unknown error") for e in payload["errors"])
        raise SoilHealthError(f"{field} failed: {messages}")

    data = (payload.get("data") or {}).get(field)
    if data is None:
        raise SoilHealthError(f"{field} returned no data")
    return data


def fetch_states(session: requests.Session) -> dict[str, str]:
    """Return {state_name: state_id}.

    The progress report has one row per state per cycle, so the same state appears
    repeatedly; keying by name collapses the duplicates. The cycle argument is
    deliberately omitted so this does not go stale when a new cycle starts.
    """
    rows = _query(session, PROGRESS_REPORT_QUERY, {}, "getProgressReportForPortal")
    states = {}
    for row in rows:
        state = row.get("state") or {}
        if state.get("name") and state.get("_id"):
            states[state["name"].strip()] = state["_id"]
    return states


def fetch_districts(session: requests.Session, state_id: str) -> dict[str, str]:
    """Return {district_name: district_id} for one state."""
    rows = _query(session, PROGRESS_REPORT_QUERY, {"state": state_id}, "getProgressReportForPortal")
    districts = {}
    for row in rows:
        district = row.get("district") or {}
        if district.get("name") and district.get("_id"):
            districts[district["name"].strip()] = district["_id"]
    return districts


def fetch_crops(session: requests.Session, state_id: str) -> list[dict]:
    """Return the crop variants a state publishes, each with its English name.

    `name` is the English crop name; the `combinedName` that older scrapers match on is
    localised per state (Kannada for Karnataka, and so on), so it cannot be matched
    against an English query.
    """
    rows = _query(session, CROP_REGISTRIES_QUERY, {"state": state_id}, "getCropRegistries")
    return [
        {
            "id": row["id"],
            "name": (row.get("name") or "").strip(),
            "variety": (row.get("variety") or "").strip(),
            "season": (row.get("season") or "").strip(),
            "irrigation_type": (row.get("irrigationType") or "").strip(),
            "recommendation_published": row.get("GFRavailable") == "Yes",
        }
        for row in rows
        if row.get("id")
    ]


def resolve_state(query: str, states: dict[str, str]) -> tuple[str, str]:
    """Match a state name to its API id."""
    match = resolve_name(query, states)
    if match is None:
        raise SoilHealthError(
            f"state '{query}' not recognised; known states: {', '.join(sorted(states))}"
        )
    return match


def resolve_district(query: str, districts: dict[str, str]) -> tuple[str, str]:
    """Match a district name to its API id within an already-resolved state."""
    match = resolve_name(query, districts)
    if match is None:
        raise SoilHealthError(
            f"district '{query}' not found in this state; districts: {', '.join(sorted(districts))}"
        )
    return match


def match_crops(crops: list[dict], query: str, season: str = "", irrigation: str = "") -> list[dict]:
    """Find the crop variants matching a crop name, narrowed by season and irrigation.

    A state publishes one row per crop x variety x season x irrigation combination, so
    "banana" matches several. Season and irrigation filters are applied only when they
    leave something behind, so an unavailable combination widens rather than returns nothing.
    """
    by_name: dict[str, set[str]] = {}
    for crop in crops:
        if crop["name"]:
            by_name.setdefault(normalize(crop["name"]), set()).add(crop["name"])
    if not by_name:
        return []

    names = best_match(normalize(query), by_name)
    if not names:
        return []

    matched = [crop for crop in crops if crop["name"] in names]
    for field, wanted in (("season", season), ("irrigation_type", irrigation)):
        if wanted.strip():
            narrowed = [c for c in matched if normalize(c[field]) == normalize(wanted)]
            if narrowed:
                matched = narrowed
            else:
                logger.info("soilhealth: no %s=%s variant, keeping all", field, wanted)

    # Prefer variants that actually have a published recommendation.
    published = [crop for crop in matched if crop["recommendation_published"]]
    matched = published or matched
    return sorted(matched, key=lambda c: (c["season"], c["irrigation_type"], c["variety"]))


def fetch_recommendations(session: requests.Session, state_id: str, district_id: str | None,
                          crop_ids: list[str], soil: dict) -> list[dict]:
    """Fetch fertilizer doses for a set of crop variants against one soil test result."""
    variables = {"state": state_id, "crops": crop_ids, "results": soil}
    if district_id:
        variables["district"] = district_id
    return _query(session, RECOMMENDATIONS_QUERY, variables, "getRecommendations")


def recommend(crop: str, state: str, soil: dict, district: str = "", season: str = "",
              irrigation: str = "") -> dict:
    """Resolve names to ids and return the raw recommendations plus what was matched.

    Returns a dict with the resolved `state`, `district`, matched `variants` and the
    API's `recommendations` list, leaving presentation to the caller.
    """
    session = new_session()
    try:
        state_name, state_id = resolve_state(state, fetch_states(session))

        district_name, district_id = "", None
        if district.strip():
            district_name, district_id = resolve_district(district, fetch_districts(session, state_id))

        crops = fetch_crops(session, state_id)
        variants = match_crops(crops, crop, season, irrigation)
        if not variants:
            available = sorted({c["name"] for c in crops})
            return {"state": state_name, "district": district_name, "variants": [],
                    "recommendations": [], "available_crops": available}

        variants = variants[:MAX_VARIANTS]
        recommendations = fetch_recommendations(
            session, state_id, district_id, [c["id"] for c in variants], soil
        )
        logger.info("soilhealth: %d recommendation(s) for %s in %s", len(recommendations), crop, state_name)
        return {"state": state_name, "district": district_name, "variants": variants,
                "recommendations": recommendations, "available_crops": []}
    except requests.RequestException as e:
        raise SoilHealthError(f"could not reach the Soil Health Card API: {e}") from e
    finally:
        session.close()
