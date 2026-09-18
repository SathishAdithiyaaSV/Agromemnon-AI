"""AgMarkNet daily mandi price source.

The ASP.NET pages (SearchCmmMkt.aspx, dropdown + GridPriceData table) that older
scrapers target now only serve a JavaScript shell — agmarknet.gov.in is a single-page
app backed by this public JSON API, which publishes the same daily market data.
"""

import datetime
import logging

import requests

from tools.matching import best_match, normalize, resolve_name

logger = logging.getLogger(__name__)

BASE_URL = "https://api.agmarknet.gov.in/v1"
STATE_PATH = "/location/state"
DAILY_REPORT_PATH = "/prices-and-arrivals/commodity-wise/daily-report-state"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Referer": "https://agmarknet.gov.in/",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
}

TIMEOUT = 60
# Reports are published a day or more behind, and not every day carries every
# commodity, so walk back until a report actually contains it.
LOOKBACK_DAYS = 10


class AgMarkNetError(Exception):
    """Raised when the upstream API cannot be reached or returns nothing usable."""


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_states(session: requests.Session) -> dict[str, int]:
    """Return {state_name_lowercase: state_id} across all pages of the state endpoint."""
    states: dict[str, int] = {}
    page = 1
    while True:
        response = session.get(f"{BASE_URL}{STATE_PATH}", params={"page": page}, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        for entry in payload.get("states", []):
            name = (entry.get("state_name") or "").strip()
            if name and entry.get("id") is not None:
                states[name.lower()] = entry["id"]
        if not payload.get("pagination", {}).get("next_page"):
            return states
        page += 1


def resolve_state(query: str, states: dict[str, int]) -> tuple[str, int]:
    """Match a state name to its API id, tolerating spelling and spacing differences."""
    match = resolve_name(query, states)
    if match is None:
        raise AgMarkNetError(f"state '{query}' not recognised; known states: {', '.join(sorted(states))}")
    return match


def _flatten(payload: dict, state_name: str, report_date: datetime.date) -> list[dict]:
    """Flatten the market > commodity group > commodity > variety tree into rows."""
    rows = []
    for market in payload.get("markets", []):
        market_name = (market.get("marketName") or "").strip()
        for group in market.get("commodityGroups", []):
            group_name = (group.get("groupName") or "").strip()
            for commodity in group.get("commodities", []):
                commodity_name = (commodity.get("commodityName") or "").strip()
                for entry in commodity.get("data", []):
                    rows.append({
                        "state": state_name,
                        "market": market_name,
                        "commodity_group": group_name,
                        "commodity": commodity_name,
                        "variety": (entry.get("variety") or "").strip(),
                        "arrivals": entry.get("arrivals"),
                        "arrivals_unit": entry.get("unitOfArrivals"),
                        "min_price": entry.get("minimumPrice"),
                        "max_price": entry.get("maximumPrice"),
                        "modal_price": entry.get("modalPrice"),
                        "price_unit": entry.get("unitOfPrice"),
                        "report_date": report_date.isoformat(),
                    })
    return rows


def fetch_daily_report(session: requests.Session, state_id: int, state_name: str,
                       report_date: datetime.date) -> list[dict]:
    """Fetch every market/commodity row a state published for one date."""
    response = session.get(
        f"{BASE_URL}{DAILY_REPORT_PATH}",
        params={"date": report_date.isoformat(), "stateIds": state_id, "includeExcel": "false"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return _flatten(response.json(), state_name, report_date)


def match_commodity(rows: list[dict], query: str) -> list[dict]:
    """Keep the rows whose commodity matches the query, by exact, substring, then fuzzy match."""
    by_name: dict[str, set[str]] = {}
    for row in rows:
        if row["commodity"]:
            by_name.setdefault(normalize(row["commodity"]), set()).add(row["commodity"])
    if not by_name:
        return []

    matched = best_match(normalize(query), by_name)
    if not matched:
        return []
    return [row for row in rows if row["commodity"] in matched]


def fetch_prices(commodity: str, state: str) -> tuple[list[dict], str]:
    """Return the most recent published rows for a commodity in a state, and the state's API name.

    Walks back from today because AgMarkNet publishes with a lag; the caller decides
    whether the date it lands on is recent enough.
    """
    session = new_session()
    try:
        states = fetch_states(session)
        state_name, state_id = resolve_state(state, states)

        today = datetime.date.today()
        for offset in range(LOOKBACK_DAYS):
            report_date = today - datetime.timedelta(days=offset)
            rows = fetch_daily_report(session, state_id, state_name, report_date)
            matched = match_commodity(rows, commodity)
            if matched:
                logger.info("agmarknet: %d rows for %s in %s on %s", len(matched), commodity, state_name, report_date)
                return matched, state_name
            logger.info("agmarknet: no %s rows for %s on %s", commodity, state_name, report_date)

        return [], state_name
    except requests.RequestException as e:
        raise AgMarkNetError(f"could not reach AgMarkNet: {e}") from e
    finally:
        session.close()
