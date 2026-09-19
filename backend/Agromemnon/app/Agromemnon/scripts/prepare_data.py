"""
Step 1: Clean the schemes CSV and turn each row into:
  - a plain-text .txt file (what gets embedded / retrieved)
  - a matching .json sidecar with metadata (for KB metadata filtering)

Bedrock Knowledge Bases support "metadata filtering" when each content file
(e.g. schemes/foo.txt) has a matching sidecar file (schemes/foo.txt.metadata.json)
containing simple key/value attributes. We use that for `level` and
`schemeCategory` so the agent can filter before/while doing semantic search.

Usage:
    python 01_prepare_data.py path/to/schemes.csv ./out
"""

import csv
import json
import re
import sys
from pathlib import Path

# Columns we actually want. Drop the stray "Null , Delete when using" column
# and any of the "unique values" / summary junk rows if they slipped into the CSV.
KEEP_COLUMNS = [
    "scheme_name",
    "slug",
    "details",
    "benefits",
    "eligibility",
    "application",
    "documents",
    "level",
    "schemeCategory",
]

LABELS = {
    "details": "Description",
    "benefits": "Benefits",
    "eligibility": "Eligibility Criteria",
    "application": "How to Apply",
    "documents": "Required Documents",
    "level": "Level",
    "schemeCategory": "Category",
}


def slugify(text: str, fallback: str) -> str:
    if not text:
        return fallback
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or fallback


def row_to_document(row: dict) -> str:
    """Turn one CSV row into a single readable text block for embedding."""
    lines = [f"Scheme: {row.get('scheme_name', '').strip()}"]
    for col in ("details", "benefits", "eligibility", "application", "documents"):
        val = (row.get(col) or "").strip()
        if val:
            lines.append(f"\n{LABELS[col]}:\n{val}")
    meta_bits = []
    if row.get("level"):
        meta_bits.append(f"Level: {row['level'].strip()}")
    if row.get("schemeCategory"):
        meta_bits.append(f"Category: {row['schemeCategory'].strip()}")
    if meta_bits:
        lines.append("\n" + " | ".join(meta_bits))
    return "\n".join(lines).strip()


def main(csv_path: str, out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    seen_slugs = set()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            name = (row.get("scheme_name") or "").strip()
            if not name:
                skipped += 1
                continue

            slug = slugify(row.get("slug", ""), fallback=f"scheme-{i}")
            # de-dupe slugs
            base_slug = slug
            n = 1
            while slug in seen_slugs:
                n += 1
                slug = f"{base_slug}-{n}"
            seen_slugs.add(slug)

            doc_text = row_to_document(row)
            if len(doc_text) < 20:
                skipped += 1
                continue

            (out / f"{slug}.txt").write_text(doc_text, encoding="utf-8")

            metadata = {
                "metadataAttributes": {
                    "scheme_name": name,
                    "slug": slug,
                    "level": (row.get("level") or "").strip() or "Unknown",
                    "schemeCategory": (row.get("schemeCategory") or "").strip() or "Unknown",
                }
            }
            (out / f"{slug}.txt.metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            written += 1

    print(f"Wrote {written} scheme documents to {out}/")
    print(f"Skipped {skipped} rows (empty name or too little content)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python 01_prepare_data.py path/to/schemes.csv ./out")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])