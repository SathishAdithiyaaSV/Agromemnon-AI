"""Clean the soil-nutrient survey CSV and load one state's rows into DynamoDB.

The published CSV is ~1 GB and covers every state as one row per
(year, village, nutrient, rating band) with a sample count. This streams it, keeps the
requested state, and rolls the counts up to village, block and district level, writing one
DynamoDB item per place and year.

Rolling up is just summing sample counts, which is why it is safe to do at load time: a
district's distribution is the sum of its villages' distributions, so no information is
invented by aggregating.

Usage:
    python scripts/load_soil_nutrients.py --csv soil-nutrient-analysis.csv --state Karnataka
    python scripts/load_soil_nutrients.py --csv ... --state Karnataka --dry-run
"""

import argparse
import csv
import logging
import os
import sys
from collections import defaultdict
from decimal import Decimal

# Imported off the tools directory rather than as tools.fertilizer, because the tools
# package __init__ imports every agent tool and so drags in the whole model stack that a
# data-loading script has no use for.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from fertilizer import nutrients, soil_store  # noqa: E402

logger = logging.getLogger("load_soil_nutrients")

# Rows whose sample total is this small describe too few fields to characterise a place;
# their distribution is mostly noise. They are still summed into the parent block and
# district, where they add real samples, but are not published as a place of their own.
MIN_SAMPLES = 10

REQUIRED_COLUMNS = {"year", "state_name", "district_name", "block_name",
                    "village_name", "nutrient_name", "nutrient_level", "value"}


def _clean(value: str) -> str:
    """Trim and collapse whitespace; the CSV has padded and double-spaced names."""
    return " ".join((value or "").strip().split())


def _count(raw: str) -> int:
    """Sample counts should be non-negative integers; anything else is dropped as dirty."""
    try:
        parsed = int(float(raw))
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def read_rows(path: str, state: str):
    """Yield cleaned (year, district, block, village, nutrient, level, count) for one state."""
    wanted = state.strip().lower()
    kept = skipped = 0

    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV is missing expected columns: {sorted(missing)}")

        for row in reader:
            if _clean(row["state_name"]).lower() != wanted:
                continue
            year = _clean(row["year"])
            district = _clean(row["district_name"])
            nutrient = _clean(row["nutrient_name"])
            level = _clean(row["nutrient_level"])
            # A row with no year, district or nutrient cannot be placed or interpreted.
            if not (year and district and nutrient and level):
                skipped += 1
                continue
            kept += 1
            yield (year, district, _clean(row["block_name"]), _clean(row["village_name"]),
                   nutrient, level, _count(row["value"]))

    logger.info("read %d %s rows (%d unusable)", kept, state, skipped)


def aggregate(rows):
    """Sum counts into {(year, granularity, place tuple): {nutrient: {level: count}}}."""
    tallies = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for year, district, block, village, nutrient, level, count in rows:
        # One row feeds every level it belongs to, so a district ends up holding the sum of
        # its villages without a second pass over the file.
        places = [("district", (district,))]
        if block:
            places.append(("block", (district, block)))
        if village:
            places.append(("village", (district, village)))

        for granularity, place in places:
            tallies[(year, granularity, place)][nutrient][level] += count

    return tallies


def build_item(state: str, year: str, granularity: str, place: tuple, counts: dict) -> dict | None:
    """Turn one place's raw counts into the DynamoDB item the tool reads back."""
    macros = {}
    for csv_name, field in nutrients.MACRO_FIELDS.items():
        levels = counts.get(csv_name, {})
        derived = nutrients.estimate(field, levels)
        if derived is None:
            continue
        value, rating, total = derived
        macros[field] = {
            "value": Decimal(str(value)),
            "level": rating,
            "samples": total,
            "distribution_percent": {
                level: share for level, share in nutrients.shares(
                    {lvl: levels.get(lvl, 0) for lvl in nutrients.MACRO_LEVELS}).items()
            },
        }

    # Without all four macros the fertilizer API cannot be called, so a partial place is
    # not worth storing.
    if len(macros) != len(nutrients.MACRO_FIELDS):
        return None

    samples = max(macro["samples"] for macro in macros.values())
    if granularity == "village" and samples < MIN_SAMPLES:
        return None

    item = {
        "pk": soil_store.partition_key(state, granularity, *place),
        "sk": year,
        "state": state.title(),
        "district": place[0].title(),
        "samples": samples,
        "macronutrients": macros,
    }
    if granularity == "block":
        item["block"] = place[1].title()
    if granularity == "village":
        item["village"] = place[1].title()

    ph = nutrients.dominant(counts.get("Soil Ph", {}), nutrients.PH_LEVELS)
    if ph:
        item["soil_ph"] = {"level": ph.lower(),
                           "distribution_percent": nutrients.shares(
                               {lvl: counts.get("Soil Ph", {}).get(lvl, 0)
                                for lvl in nutrients.PH_LEVELS})}

    ec = nutrients.dominant(counts.get("Electrical Conductivity", {}), nutrients.EC_LEVELS)
    if ec:
        item["salinity"] = {"level": ec.lower()}

    # Only the deficient share is stored; "how short is this area" is the actionable half,
    # and the sufficient share is just its complement.
    deficient = {}
    for micro in nutrients.MICRO_NUTRIENTS:
        levels = counts.get(micro, {})
        total = sum(levels.get(lvl, 0) for lvl in nutrients.MICRO_LEVELS)
        if total:
            deficient[micro.lower()] = round(100 * levels.get("Deficient", 0) / total)
    if deficient:
        item["micronutrient_deficient_percent"] = deficient

    return item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to the soil nutrient CSV.")
    parser.add_argument("--state", default="Karnataka", help="State to load.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Aggregate and report without writing to DynamoDB.")
    parser.add_argument("--table", help="Override the target table name.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.table:
        soil_store.TABLE_NAME = args.table

    tallies = aggregate(read_rows(args.csv, args.state))
    logger.info("aggregated %d place-years", len(tallies))

    items, dropped = [], 0
    for (year, granularity, place), counts in tallies.items():
        item = build_item(args.state, year, granularity, place, counts)
        if item is None:
            dropped += 1
            continue
        items.append(item)

    by_granularity = defaultdict(int)
    for item in items:
        by_granularity[item["pk"].split("#")[1]] += 1
    logger.info("built %d items (%s), dropped %d thin/partial places",
                len(items), dict(by_granularity), dropped)

    if not items:
        logger.error("nothing to write — check --state spelling against the CSV")
        return 1

    sample = min(items, key=lambda i: i["pk"])
    logger.info("example item: %s", sample)

    if args.dry_run:
        logger.info("dry run — nothing written")
        return 0

    written = soil_store.write_places(items)
    logger.info("wrote %d/%d items to %s", written, len(items), soil_store.TABLE_NAME)
    return 0 if written == len(items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
