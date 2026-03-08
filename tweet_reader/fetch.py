from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any, Optional

import requests

from .models import LinkEvidence
from .parse import extract_tweet_id

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_syndication(tweet_url: str, timeout: int = 20) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        return None, "Could not extract tweet id from URL"

    token = _build_syndication_token(tweet_id)
    try:
        response = requests.get(
            "https://cdn.syndication.twimg.com/tweet-result",
            params={"id": tweet_id, "token": token},
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return None, f"syndication request failed with status {response.status_code}"
        payload = response.json()
        if not isinstance(payload, dict):
            return None, "syndication response was not a JSON object"
        return payload, None
    except requests.RequestException as exc:
        return None, f"syndication request error: {exc}"
    except ValueError as exc:
        return None, f"syndication JSON parse error: {exc}"


def fetch_oembed(tweet_url: str, timeout: int = 20) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        response = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": tweet_url, "omit_script": "1"},
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return None, f"oEmbed request failed with status {response.status_code}"
        payload = response.json()
        if not isinstance(payload, dict):
            return None, "oEmbed response was not a JSON object"
        return payload, None
    except requests.RequestException as exc:
        return None, f"oEmbed request error: {exc}"
    except ValueError as exc:
        return None, f"oEmbed JSON parse error: {exc}"


def fetch_html(tweet_url: str, timeout: int = 20) -> tuple[Optional[str], Optional[str]]:
    try:
        response = requests.get(
            tweet_url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return None, f"HTML request failed with status {response.status_code}"
        return response.text, None
    except requests.RequestException as exc:
        return None, f"HTML request error: {exc}"


def enrich_link_evidence(link_evidence: list[LinkEvidence], timeout: int = 20) -> list[LinkEvidence]:
    enriched: list[LinkEvidence] = []
    for item in link_evidence:
        target_url = item.expanded_url or item.url
        if not target_url or item.kind == "media" or item.resolved_url:
            enriched.append(item)
            continue

        resolved_url, content_type, error = _resolve_url_metadata(target_url, timeout=timeout)
        enriched.append(
            replace(
                item,
                resolved_url=resolved_url,
                content_type=content_type,
                resolution_error=error,
            )
        )
    return enriched


def _resolve_url_metadata(url: str, timeout: int = 20) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        content_type = _clean_content_type(response.headers.get("Content-Type"))
        resolved_url = response.url
        response.close()
        return resolved_url, content_type, None
    except requests.RequestException as exc:
        return None, None, str(exc)


def _build_syndication_token(tweet_id: str) -> str:
    numeric_value = (float(tweet_id) / 1e15) * math.pi
    raw = _float_to_base36(numeric_value)
    return re.sub(r"(0+|\.)", "", raw)


def _float_to_base36(value: float, precision: int = 24) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    integer_part = int(value)
    fractional_part = value - integer_part

    if integer_part == 0:
        output = "0"
    else:
        digits: list[str] = []
        while integer_part:
            integer_part, remainder = divmod(integer_part, 36)
            digits.append(alphabet[remainder])
        output = "".join(reversed(digits))

    output += "."
    for _ in range(precision):
        fractional_part *= 36
        digit = int(fractional_part)
        output += alphabet[digit]
        fractional_part -= digit
    return output


def _clean_content_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower() or None
