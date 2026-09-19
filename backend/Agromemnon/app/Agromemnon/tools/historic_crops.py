import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from strands import tool

import secret_store


DATA_GOV_RESOURCE_ID = "35be999b-0208-4354-b557-f6ca9a5355de"
DATA_GOV_API_URL = f"https://api.data.gov.in/resource/{DATA_GOV_RESOURCE_ID}"
REQUEST_TIMEOUT_SECONDS = 15
PAGE_SIZE = 1000
MAX_PAGES = 10

def _request_records(location: str, season: str, offset: int = 0) -> dict:
    api_key = secret_store.resolve("DATA_GOV_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DATA_GOV_API_KEY is not configured. Create an API key at data.gov.in, then "
            "set DATA_GOV_API_KEY locally or point DATA_GOV_API_KEY_SECRET at a Secrets "
            "Manager secret for a deployed runtime."
        )

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": offset,
        # The resource's own field names are lower_snake_case, and data.gov.in silently
        # returns an empty page for a filter naming a field that does not exist. Sending
        # "District_Name" therefore did not narrow the query — it matched nothing, for
        # every district, every time. The values are stored upper-case ("BAGALKOT") and
        # the filter compares exactly, so the district has to be folded up to match while
        # the season is stored title-case and must not be.
        "filters[district_name]": location.upper(),
    }
    if season:
        params["filters[season]"] = season.strip().title()

    request = Request(
        f"{DATA_GOV_API_URL}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "Agromemnon/1.0"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            error_body = json.load(error)
            message = error_body.get("error", error_body.get("message", str(error)))
        except (json.JSONDecodeError, OSError):
            message = str(error)
        raise RuntimeError(f"data.gov.in request failed: {message}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"data.gov.in is unavailable: {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("data.gov.in returned invalid JSON") from error


def _field(record: dict, *names: str):
    lowered = {str(key).casefold(): value for key, value in record.items()}
    for name in names:
        value = lowered.get(name.casefold())
        if value not in (None, "", "NA", "N/A", "-", "null"):
            return value
    return None


def _number(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _normalize_record(record: dict) -> dict:
    # "area_" and "production_" are what this resource actually calls them, trailing
    # underscore and all. Without them every row parsed to a null area and production,
    # so the tool returned crop names with no figures attached — and NO_INVENTION
    # correctly stops the agent inventing the numbers to fill the gap.
    area = _number(_field(record, "area_", "Area", "Area (Hectares)"))
    production = _number(_field(record, "production_", "Production", "Production (Tonnes)"))
    calculated_yield = production * 1000 / area if area and production is not None else None
    return {
        "state": _field(record, "State_Name", "State", "State Name"),
        "district": _field(record, "District_Name", "District", "District Name"),
        "crop_year": _field(record, "Crop_Year", "Crop Year", "Year"),
        "season": _field(record, "Season"),
        "crop": _field(record, "Crop", "Crop Name"),
        "area_hectares": area,
        "production_tonnes": production,
        "yield_kg_per_hectare": calculated_yield,
    }


@tool
def historic_crops(location: str, season: str = "") -> str:
    """Get official historical crop production records for an Indian district.

    Data is retrieved live from India's data.gov.in resource "District-wise,
    season-wise crop production statistics from 1997". Yield is calculated from
    the published production and area values when the source does not provide it.

    Args:
        location: District name, for example "Bengaluru Urban" or "Haveri".
        season: Optional season, for example "Kharif", "Rabi", or "Whole Year".
    """
    if not isinstance(location, str) or not location.strip():
        raise ValueError("location must be a non-empty Indian district name")
    if not isinstance(season, str):
        raise ValueError("season must be a string")

    records = []
    for page_number in range(MAX_PAGES):
        response = _request_records(location.strip(), season.strip(), page_number * PAGE_SIZE)
        page_records = response.get("records", [])
        if not isinstance(page_records, list):
            raise RuntimeError("data.gov.in response did not contain a records list")
        records.extend(page_records)
        if len(page_records) < PAGE_SIZE:
            break

    normalized = [_normalize_record(record) for record in records if isinstance(record, dict)]
    normalized.sort(key=lambda record: str(record.get("crop_year") or ""), reverse=True)
    return json.dumps({
        "source": "https://www.data.gov.in/resource/district-wise-season-wise-crop-production-statistics-1997",
        "location_requested": location.strip(),
        "season_requested": season.strip() or None,
        "record_count": len(normalized),
        "records": normalized,
    }, ensure_ascii=True)

