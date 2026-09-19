"""DynamoDB storage for the government soil-nutrient survey.

Table (see infra/soil-nutrients-table.yaml):
  pk = "<state>#<level>#<place path>"   e.g. "karnataka#district#belagavi"
                                            "karnataka#block#belagavi#athani"
                                            "karnataka#village#belagavi#ugarkhurd"
  sk = "<survey year>"                  e.g. "2024-25", so sorting backwards gives the newest

Three granularities share one table so a lookup is a single query at whichever level the
farmer named. Village rows are keyed by district rather than by block, because a farmer
naming their village rarely names the block it sits in; the loader merges same-named
villages within a district, which is harmless since they are neighbours.

Reads degrade to "no data" rather than raising, so the fertilizer tool can still fall back
to asking for a soil test when the table is missing or credentials are absent.
"""

import logging
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("SOIL_NUTRIENTS_TABLE", "Agromemnon-soil-nutrients")

# Lookup order. A village row describes the farmer's own surroundings; a district row is a
# wide average, but still better than refusing to answer.
GRANULARITIES = ("village", "block", "district")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def _slug(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def partition_key(state: str, granularity: str, *place: str) -> str:
    parts = [_slug(state), granularity, *(_slug(p) for p in place)]
    return "#".join(parts)


def _to_number(value):
    """Decimal -> int for whole numbers (sample counts), float otherwise (nutrient values)."""
    if not isinstance(value, Decimal):
        return value
    return int(value) if value == value.to_integral_value() else float(value)


def _decode(value):
    """Undo DynamoDB's Decimal encoding at any depth.

    The nutrient payload nests three levels deep (macronutrients -> nitrogen ->
    distribution_percent -> Low), and a Decimal left anywhere in there is not JSON
    serialisable, so the tool result would fail to serialise rather than return.
    """
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items() if k not in ("pk", "sk")}
    if isinstance(value, (list, set)):
        return [_decode(v) for v in value]
    return _to_number(value)


def read_latest(state: str, granularity: str, *place: str) -> dict | None:
    """Return the newest survey year for one place, or None if it was never surveyed."""
    pk = partition_key(state, granularity, *place)
    try:
        items = _get_table().query(
            KeyConditionExpression=Key("pk").eq(pk),
            ScanIndexForward=False,
            Limit=1,
        ).get("Items", [])
    except (BotoCoreError, ClientError) as e:
        logger.warning("soil nutrient table unavailable for read (%s): %s", TABLE_NAME, e)
        return None

    if not items:
        return None
    row = _decode(items[0])
    row["survey_year"] = items[0]["sk"]
    row["granularity"] = granularity
    return row


def find(state: str, district: str = "", block: str = "", village: str = "") -> dict | None:
    """Look up the most specific place that was surveyed, narrowest first.

    Village and block are only tried when a district is known, because both names repeat
    across districts and a bare match could land in the wrong part of the state.
    """
    if not _slug(state):
        return None

    candidates = []
    if _slug(district):
        if _slug(village):
            candidates.append(("village", (district, village)))
        if _slug(block):
            candidates.append(("block", (district, block)))
        candidates.append(("district", (district,)))

    for granularity, place in candidates:
        row = read_latest(state, granularity, *place)
        if row:
            return row
    return None


def write_places(rows: list[dict]) -> int:
    """Store aggregated rows. Each needs pk, sk and its nutrient payload already built."""
    written = 0
    try:
        table = _get_table()
        with table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
            for row in rows:
                batch.put_item(Item=row)
                written += 1
    except (BotoCoreError, ClientError) as e:
        logger.warning("could not write %d soil rows to %s: %s", len(rows), TABLE_NAME, e)
        return written
    logger.info("stored %d soil nutrient rows in %s", written, TABLE_NAME)
    return written
