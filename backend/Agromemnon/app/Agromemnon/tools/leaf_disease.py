"""Look up the treatment for a disease the vision model identified from the photo.

There is no trained classifier behind this any more. plant_doctor reads the
photograph with a Bedrock vision model and names the disease itself; this tool's
only job is to supply the cultural steps and the spray rates for that name.

The split matters because of the shared no-invention guardrail. The model may
identify a disease from what it can see — that is a judgement about an image, and
it is the one thing a vision model is for. It may not produce "3 g per litre" from
memory, because a wrong dose reads exactly like a right one to the farmer buying
the product. So identification comes from the model and every number comes from
tools/leaf_disease_treatments.py.

Matching is deliberately forgiving. The model will write "early blight", "Early
Blight (Alternaria solani)" or "tomato early blight" for the same record, and a
dict lookup that misses on capitalisation would send the agent back empty-handed
to a farmer holding a diagnosis.
"""

import logging
import re

from rapidfuzz import fuzz, process
from strands import tool

from tools.leaf_disease_treatments import TREATMENTS, for_label

logger = logging.getLogger(__name__)

# Below this the match is a different disease, not a differently-worded one. Set
# high because the covered names are short and similar to each other — "early
# blight" and "late blight" share most of their characters but not their cure.
MATCH_THRESHOLD = 82

# Words that carry no signal for matching: every record is a tomato leaf disease,
# so leaving them in pulls every query toward every record.
_NOISE = re.compile(
    r"\b(tomato|leaf|leaves|plant|disease|infection|blight|spot|virus|mould|mold)\b"
)


def _aliases(label: str) -> set[str]:
    """Every wording that should resolve to this record.

    Both the common name and the dataset key, because they disagree on plurals and
    word order — the mite record is keyed "Spider_mites Two-spotted_spider_mite"
    but named "Two-spotted spider mite", and a model writing the obvious "spider
    mites" matches the key and not the name.
    """
    key_words = label.replace("Tomato___", "").replace("_", " ").lower()
    return {TREATMENTS[label]["common_name"].lower(), key_words}


_BY_ALIAS = {alias: label for label in TREATMENTS for alias in _aliases(label)}


def _normalise(text: str) -> str:
    text = text.lower().replace("_", " ")
    # Drop a parenthesised pathogen, e.g. "early blight (Alternaria solani)".
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("tomato___", " ")
    return re.sub(r"\s+", " ", text).strip()


def _match(disease: str) -> str | None:
    """Resolve free-text wording to a TREATMENTS key, or None when nothing is close."""
    if disease in TREATMENTS:
        return disease

    query = _normalise(disease)
    if not query:
        return None
    if query in _BY_ALIAS:
        return _BY_ALIAS[query]

    # Two passes: the full wording first, then with the filler words stripped. The
    # full wording wins ties, because "late blight" beating "early blight" on a
    # query of "tomato late blight" depends on the word that the second pass drops.
    for candidate in (query, _NOISE.sub(" ", query).strip()):
        if not candidate:
            continue
        hit = process.extractOne(
            candidate, _BY_ALIAS.keys(), scorer=fuzz.token_set_ratio,
            score_cutoff=MATCH_THRESHOLD,
        )
        if hit:
            return _BY_ALIAS[hit[0]]
    return None


@tool
def disease_treatment(disease: str) -> dict:
    """Get the treatment for a tomato leaf disease you have identified from the photo.

    Returns the cultural steps and the chemical options with their rates, from the
    crop advisory's tomato disease reference. Call this after you have looked at the
    photograph and decided what the disease is — every dose in your answer must come
    from this result.

    Args:
        disease: The disease you identified, in plain words, e.g. "early blight",
            "leaf mold", "tomato yellow leaf curl virus". Use "healthy" when the
            leaf shows no disease.
    """
    if not disease.strip():
        return {
            "error": "no_disease_given",
            "message": "Name the disease you identified from the photo.",
            "covered": sorted(_BY_ALIAS),
        }

    label = _match(disease)
    if label is None:
        logger.info("no treatment record matched %r", disease)
        return {
            "error": "not_covered",
            "message": (
                f"The tomato disease reference has no record for '{disease}'. Give the "
                "farmer your identification and what they can see, tell them the exact "
                "spray rate is not on file, and send them to their KVK for the product "
                "and dose. Do not give a dose from your own knowledge."
            ),
            "covered": sorted(_BY_ALIAS),
        }

    record = for_label(label)
    return {
        "crop": "tomato",
        "diagnosis": record["common_name"],
        "matched_from": disease,
        "treatment": record,
        "scope": (
            "This reference covers tomato only. If the photo was not a tomato, say so "
            "rather than applying a tomato treatment to another crop."
        ),
    }
