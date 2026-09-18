"""Fuzzy name matching shared by tools that resolve free-text names to API ids.

Farmers and the model spell place and crop names loosely ("tamilnadu", "Tamil Nadu",
"TAMILNADU"), while the government APIs only accept their own exact spellings.
"""

import re

from rapidfuzz import fuzz, process

# Below this score a match is more likely wrong than right, and a wrong crop or
# district silently returns confident advice about the wrong thing.
MATCH_THRESHOLD = 70


def normalize(value: str) -> str:
    """Strip case, spacing and punctuation so "tamilnadu" matches "Tamil Nadu"."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def best_match(wanted: str, candidates: dict):
    """Resolve a normalized name against normalized candidate keys.

    Tries exact, then substring, then fuzzy matching, and returns the matching
    candidate's value, or None when nothing clears MATCH_THRESHOLD.
    """
    if wanted in candidates:
        return candidates[wanted]

    contained = [key for key in candidates if wanted and (wanted in key or key in wanted)]
    if contained:
        best = process.extractOne(wanted, contained, scorer=fuzz.WRatio)
        return candidates[best[0] if best else contained[0]]

    fuzzy = process.extractOne(wanted, list(candidates), scorer=fuzz.WRatio, score_cutoff=MATCH_THRESHOLD)
    return candidates[fuzzy[0]] if fuzzy else None


def resolve_name(query: str, options: dict):
    """Match a free-text name against {api_name: value}, returning (api_name, value) or None."""
    by_name = {normalize(name): name for name in options}
    matched = best_match(normalize(query), by_name)
    return (matched, options[matched]) if matched is not None else None
