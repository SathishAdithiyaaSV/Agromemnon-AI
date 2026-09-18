"""DynamoDB storage for scraped mandi prices.

Table (see infra/mandi-prices-table.yaml):
  pk = "<state>#<commodity>"            partition per commodity in a state
  sk = "<report_date>#<market>#<variety>"   ISO date first, so sorting by sk sorts by date

Every helper degrades to "no data" rather than raising, so the tool still answers from
a live scrape when the table has not been deployed or credentials are missing.
"""

import logging
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("MANDI_PRICES_TABLE", "Agromemnon-mandi-prices")

_NUMERIC_FIELDS = ("arrivals", "min_price", "max_price", "modal_price")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def partition_key(commodity: str, state: str) -> str:
    return f"{state.strip().lower()}#{commodity.strip().lower()}"


def _sort_key(row: dict) -> str:
    return f"{row['report_date']}#{row.get('market', '')}#{row.get('variety', '')}"


def _decode(item: dict) -> dict:
    row = {k: v for k, v in item.items() if k not in ("pk", "sk")}
    for field in _NUMERIC_FIELDS:
        if isinstance(row.get(field), Decimal):
            row[field] = float(row[field])
    return row


def read_latest(commodity: str, state: str) -> tuple[list[dict], str | None, str | None]:
    """Return the rows carrying the most recent report date, that date, and when they were fetched."""
    pk = partition_key(commodity, state)
    try:
        table = _get_table()
        newest = table.query(
            KeyConditionExpression=Key("pk").eq(pk),
            ScanIndexForward=False,
            Limit=1,
        ).get("Items", [])
        if not newest:
            return [], None, None

        report_date = newest[0]["sk"].split("#", 1)[0]
        items = table.query(
            KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with(f"{report_date}#"),
        ).get("Items", [])
    except (BotoCoreError, ClientError) as e:
        logger.warning("mandi price table unavailable for read (%s): %s", TABLE_NAME, e)
        return [], None, None

    rows = [_decode(item) for item in items]
    fetched_on = max((row.get("fetched_on") or "" for row in rows), default="") or None
    return rows, report_date, fetched_on


def write_prices(commodity: str, state: str, rows: list[dict], fetched_on: str) -> None:
    """Store scraped rows, overwriting any existing row for the same date/market/variety."""
    pk = partition_key(commodity, state)
    try:
        table = _get_table()
        with table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
            for row in rows:
                item = {"pk": pk, "sk": _sort_key(row), "fetched_on": fetched_on}
                for key, value in row.items():
                    if value is None or value == "":
                        continue
                    item[key] = Decimal(str(value)) if key in _NUMERIC_FIELDS else value
                batch.put_item(Item=item)
    except (BotoCoreError, ClientError) as e:
        logger.warning("could not write %d rows to %s: %s", len(rows), TABLE_NAME, e)
    else:
        logger.info("stored %d mandi price rows in %s", len(rows), TABLE_NAME)
