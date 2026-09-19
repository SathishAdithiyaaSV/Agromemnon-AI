"""YouTube search without the Data API.

The public Data API needs a Google Cloud project, a key per deployment and has a
10k-unit/day quota that a search burns 100 units at a time. Instead this reads the
same data youtube.com itself renders with:

1. the search results page, whose `ytInitialData` blob holds the full result list, and
2. InnerTube (`/youtubei/v1/search`) — the JSON endpoint the site's own JavaScript
   calls — as a fallback when the HTML layout shifts.

Both return `videoRenderer` objects, so one parser covers them.
"""

import json
import re
import time
from typing import Any, Iterator, Optional

import requests
from strands import tool

SEARCH_URL = "https://www.youtube.com/results"
INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/search"
# Public web-client identity that youtube.com sends with its own requests.
INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
INNERTUBE_CLIENT = {"clientName": "WEB", "clientVersion": "2.20240401.00.00"}
# sp=EgIQAQ%3D%3D — restrict results to videos (no channels, playlists or shelves).
VIDEOS_ONLY = "EgIQAQ%3D%3D"

REQUEST_TIMEOUT_SECONDS = 10
MAX_RESULTS = 10
MIN_DURATION_SECONDS = 70  # drop Shorts: too short to teach anything
CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 128

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# SOCS/CONSENT skip the EU consent interstitial, which otherwise replaces the results page.
COOKIES = {"SOCS": "CAI", "CONSENT": "YES+1"}

_cache: dict[tuple, tuple[float, str]] = {}


def _cache_get(key: tuple) -> Optional[str]:
    hit = _cache.get(key)
    if hit is None:
        return None
    stored_at, value = hit
    if time.time() - stored_at > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: tuple, value: str) -> None:
    if len(_cache) >= CACHE_MAX_ENTRIES:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    _cache[key] = (time.time(), value)


def _extract_initial_data(html: str) -> dict:
    """Pull the ytInitialData JSON object out of the results page HTML."""
    match = re.search(r"ytInitialData\s*=\s*", html)
    if not match:
        raise RuntimeError("search page did not contain ytInitialData")
    # The blob ends with `;</script>`, but it also contains braces and escaped quotes,
    # so decode it as JSON from its opening brace instead of matching the end by regex.
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(html[match.end():].lstrip())
    return data


def _walk_video_renderers(node: Any) -> Iterator[dict]:
    """Yield every videoRenderer in the response, whatever section it is nested in."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "videoRenderer" and isinstance(value, dict):
                yield value
            else:
                yield from _walk_video_renderers(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_video_renderers(item)


def _text(node: Any) -> str:
    """Flatten YouTube's two text shapes: {simpleText} and {runs: [{text}]}."""
    if not isinstance(node, dict):
        return ""
    if isinstance(node.get("simpleText"), str):
        return node["simpleText"]
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(run.get("text", "") for run in runs if isinstance(run, dict))
    return ""


def _duration_seconds(label: str) -> Optional[int]:
    parts = label.split(":")
    if not label or not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def _view_count(label: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", label)
    return int(digits) if digits else None


def _is_live(renderer: dict) -> bool:
    badges = json.dumps(renderer.get("badges", [])) + json.dumps(renderer.get("thumbnailOverlays", []))
    return "LIVE" in badges.upper()


def _parse_results(data: dict, limit: int) -> list[dict]:
    videos = []
    seen = set()

    for renderer in _walk_video_renderers(data):
        video_id = renderer.get("videoId")
        title = _text(renderer.get("title"))
        if not video_id or not title or video_id in seen:
            continue

        duration_label = _text(renderer.get("lengthText"))
        duration = _duration_seconds(duration_label)
        # A missing duration means a live stream or premiere — not a tutorial.
        if duration is None or duration < MIN_DURATION_SECONDS or _is_live(renderer):
            continue

        snippets = renderer.get("detailedMetadataSnippets") or []
        description = _text(snippets[0].get("snippetText")) if snippets else ""

        seen.add(video_id)
        videos.append({
            "video_id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "channel": _text(renderer.get("ownerText")) or _text(renderer.get("longBylineText")),
            "duration": duration_label,
            "duration_seconds": duration,
            "views": _view_count(_text(renderer.get("viewCountText"))),
            "published": _text(renderer.get("publishedTimeText")),
            "description": description,
        })
        if len(videos) >= limit:
            break

    return videos


def _search_html(query: str, language: str, region: str) -> dict:
    response = requests.get(
        SEARCH_URL,
        params={"search_query": query, "sp": VIDEOS_ONLY, "hl": language, "gl": region},
        headers={"User-Agent": USER_AGENT, "Accept-Language": f"{language},en;q=0.8"},
        cookies=COOKIES,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _extract_initial_data(response.text)


def _search_innertube(query: str, language: str, region: str) -> dict:
    response = requests.post(
        INNERTUBE_URL,
        params={"key": INNERTUBE_KEY},
        json={
            "query": query,
            "params": VIDEOS_ONLY,
            "context": {"client": {**INNERTUBE_CLIENT, "hl": language, "gl": region}},
        },
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


@tool
def youtube_search(query: str, language: str = "en", region: str = "IN", limit: int = 5) -> str:
    """Search YouTube for videos on a topic and return the top matches as JSON.

    Args:
        query: What to search for, e.g. "tomato leaf curl virus treatment".
        language: Two-letter language code for the results, e.g. "hi", "kn", "ta", "en".
        region: Two-letter country code, e.g. "IN".
        limit: How many videos to return (1-10).
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty search string")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
    if not re.fullmatch(r"[A-Za-z]{2}", language or "") or not re.fullmatch(r"[A-Za-z]{2}", region or ""):
        raise ValueError("language and region must be two-letter codes, e.g. 'hi' and 'IN'")

    query = query.strip()
    language, region = language.lower(), region.upper()

    cache_key = (query.lower(), language, region, limit)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    errors = []
    for search in (_search_html, _search_innertube):
        try:
            videos = _parse_results(search(query, language, region), limit)
        except (requests.RequestException, ValueError, RuntimeError, KeyError) as error:
            errors.append(f"{search.__name__}: {error}")
            continue
        if videos:
            result = json.dumps({"query": query, "language": language, "results": videos}, ensure_ascii=False)
            _cache_put(cache_key, result)
            return result
        errors.append(f"{search.__name__}: no videos in response")

    return json.dumps({"query": query, "language": language, "results": [], "errors": errors}, ensure_ascii=False)
