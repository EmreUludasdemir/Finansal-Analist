from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import LinkEvidence, TweetData

TWEET_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]{1,15}/status/\d+(?:[/?#].*)?$",
    re.IGNORECASE,
)

LOGIN_MARKERS = [
    "log in to x",
    "log in to twitter",
    "sign up for x",
    "sign up for twitter",
    "join x",
    "x.com/login",
    "twitter.com/login",
    "something went wrong",
    "enable javascript",
    "javascript is not available",
    "unusual activity",
]

GENERIC_MARKERS = [
    "cookie policy",
    "privacy policy",
    "terms of service",
    "help center",
]

THREAD_RE = re.compile(r"^\s*\d{1,3}\s*(?:/|\.|\))\s+.+$")
TEXT_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


def validate_tweet_url(url: str) -> bool:
    return bool(TWEET_URL_RE.match(url.strip()))


def extract_tweet_id(url: str) -> Optional[str]:
    match = re.search(r"/status/(\d+)", url.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def parse_syndication(url: str, payload: dict[str, Any]) -> TweetData:
    text = _normalize_text(str(payload.get("text", "")).strip())
    author = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    author_name = _safe_str(author.get("name"))
    author_handle = _safe_str(author.get("screen_name"))
    timestamp = _safe_str(payload.get("created_at"))
    reasons = _confidence_reasons(text)
    confidence = "low" if reasons else "high"

    return TweetData(
        url=url,
        tweet_id=_safe_str(payload.get("id_str")) or extract_tweet_id(url),
        author_name=author_name,
        author_handle=author_handle,
        timestamp=timestamp,
        text=text,
        thread_items=_extract_thread_items(text),
        confidence=confidence,
        confidence_reasons=reasons,
        source="syndication",
        link_evidence=_extract_link_evidence_from_syndication(payload),
    )


def parse_oembed(url: str, payload: dict[str, Any]) -> TweetData:
    html_fragment = str(payload.get("html", "")).strip()
    author_name = _safe_str(payload.get("author_name"))
    author_handle = _extract_handle(_safe_str(payload.get("author_url"))) or _extract_handle(author_name)
    timestamp = _extract_oembed_timestamp(html_fragment)
    text = _extract_oembed_text(html_fragment)

    reasons = _confidence_reasons(text, html_fragment=html_fragment)
    confidence = "low" if reasons else "high"

    return TweetData(
        url=url,
        tweet_id=extract_tweet_id(url),
        author_name=author_name,
        author_handle=author_handle,
        timestamp=timestamp,
        text=text,
        thread_items=_extract_thread_items(text),
        confidence=confidence,
        confidence_reasons=reasons,
        source="oembed",
        link_evidence=_extract_text_link_evidence(text),
    )


def parse_html(url: str, html: str) -> TweetData:
    soup = BeautifulSoup(html, "html.parser")

    author_name = _meta_content(soup, "meta[name='author']")
    if not author_name:
        author_name = _extract_author_from_title(_meta_content(soup, "meta[property='og:title']"))
    if not author_name:
        author_name = _extract_author_from_title(_meta_content(soup, "meta[name='twitter:title']"))

    author_handle = (
        _meta_content(soup, "meta[property='profile:username']")
        or _extract_handle(_meta_content(soup, "meta[name='twitter:site']"))
        or _extract_handle_from_url(url)
    )

    timestamp = (
        _extract_timestamp_from_jsonld(soup)
        or _meta_content(soup, "meta[property='article:published_time']")
        or _meta_content(soup, "meta[property='og:updated_time']")
        or _extract_timestamp_from_time_tag(soup)
    )

    text = _extract_html_text(soup)
    reasons = _confidence_reasons(text, html=html)
    confidence = "low" if reasons else "high"

    return TweetData(
        url=url,
        tweet_id=extract_tweet_id(url),
        author_name=author_name,
        author_handle=author_handle,
        timestamp=timestamp,
        text=text,
        thread_items=_extract_thread_items(text),
        confidence=confidence,
        confidence_reasons=reasons,
        source="html",
        link_evidence=_extract_text_link_evidence(text),
    )


def parse_manual_paste(url: str, raw_text: str) -> TweetData:
    normalized_raw = raw_text.lstrip("\ufeff")
    lines = normalized_raw.replace("\r\n", "\n").split("\n")
    author_name: Optional[str] = None
    author_handle: Optional[str] = None
    timestamp: Optional[str] = None
    content_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("author:") and author_name is None:
            author_name = stripped.split(":", 1)[1].strip() or None
            continue
        if lower.startswith("handle:") and author_handle is None:
            author_handle = _extract_handle(stripped.split(":", 1)[1].strip())
            continue
        if lower.startswith("timestamp:") and timestamp is None:
            timestamp = stripped.split(":", 1)[1].strip() or None
            continue
        content_lines.append(line)

    text = _normalize_text("\n".join(content_lines).strip())
    reasons = _confidence_reasons(text, html=None, html_fragment=None)
    confidence = "low" if reasons else "high"

    return TweetData(
        url=url,
        tweet_id=extract_tweet_id(url),
        author_name=author_name,
        author_handle=author_handle,
        timestamp=timestamp,
        text=text,
        thread_items=_extract_thread_items(text),
        confidence=confidence,
        confidence_reasons=reasons,
        source="manual_paste",
        link_evidence=_extract_text_link_evidence(text),
    )


def _extract_oembed_text(html_fragment: str) -> str:
    if not html_fragment:
        return ""
    soup = BeautifulSoup(html_fragment, "html.parser")
    blockquote = soup.find("blockquote")
    if blockquote is None:
        return _normalize_text(soup.get_text("\n", strip=True))

    paragraphs = blockquote.find_all("p")
    if paragraphs:
        parts = [p.get_text("\n", strip=True) for p in paragraphs]
        return _normalize_text("\n".join(part for part in parts if part))

    text = blockquote.get_text("\n", strip=True)
    lines = [line for line in text.splitlines() if line.strip()]
    filtered = [line for line in lines if not line.startswith(("-", "\u2014"))]
    return _normalize_text("\n".join(filtered))


def _extract_oembed_timestamp(html_fragment: str) -> Optional[str]:
    if not html_fragment:
        return None
    soup = BeautifulSoup(html_fragment, "html.parser")
    blockquote = soup.find("blockquote")
    if blockquote is None:
        return None
    anchors = blockquote.find_all("a")
    if not anchors:
        return None
    value = anchors[-1].get_text(" ", strip=True)
    return value or None


def _extract_html_text(soup: BeautifulSoup) -> str:
    candidates: list[str] = []

    for selector in [
        "meta[property='og:description']",
        "meta[name='twitter:description']",
        "meta[name='description']",
    ]:
        value = _meta_content(soup, selector)
        if value:
            candidates.append(value)

    for node in soup.select("[data-testid='tweetText']"):
        value = node.get_text("\n", strip=True)
        if value:
            candidates.append(value)

    article = soup.find("article")
    if article is not None:
        value = article.get_text("\n", strip=True)
        if value:
            candidates.append(value)

    body = soup.find("body")
    if body is not None:
        value = body.get_text("\n", strip=True)
        if value:
            candidates.append(value)

    cleaned = [_normalize_text(item) for item in candidates if item and item.strip()]
    if not cleaned:
        return ""

    # Keep the longest meaningful candidate to avoid shell snippets.
    return max(cleaned, key=len)


def _extract_thread_items(text: str) -> list[str]:
    if not text:
        return []
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if THREAD_RE.match(stripped):
            items.append(stripped)
    return items


def _extract_link_evidence_from_syndication(payload: dict[str, Any]) -> list[LinkEvidence]:
    links: list[LinkEvidence] = []
    entities = payload.get("entities")
    if not isinstance(entities, dict):
        return links

    urls = entities.get("urls")
    if isinstance(urls, list):
        for item in urls:
            if not isinstance(item, dict):
                continue
            raw_url = _safe_str(item.get("url"))
            if not raw_url:
                continue
            links.append(
                LinkEvidence(
                    url=raw_url,
                    expanded_url=_safe_str(item.get("expanded_url")),
                    display_url=_safe_str(item.get("display_url")),
                    kind="external",
                )
            )

    media_items = entities.get("media")
    media_details = payload.get("mediaDetails")
    details_by_url: dict[str, dict[str, Any]] = {}
    if isinstance(media_details, list):
        for detail in media_details:
            if not isinstance(detail, dict):
                continue
            key = _safe_str(detail.get("url"))
            if key:
                details_by_url[key] = detail

    if isinstance(media_items, list):
        for item in media_items:
            if not isinstance(item, dict):
                continue
            raw_url = _safe_str(item.get("url"))
            if not raw_url:
                continue
            detail = details_by_url.get(raw_url, {})
            links.append(
                LinkEvidence(
                    url=raw_url,
                    expanded_url=_safe_str(item.get("expanded_url")),
                    display_url=_safe_str(item.get("display_url")),
                    resolved_url=_safe_str(detail.get("media_url_https")),
                    content_type=_coerce_media_content_type(_safe_str(detail.get("type"))),
                    kind="media",
                )
            )

    return links


def _extract_text_link_evidence(text: str) -> list[LinkEvidence]:
    seen: set[str] = set()
    evidence: list[LinkEvidence] = []
    for match in TEXT_URL_RE.findall(text):
        url = _strip_trailing_punctuation(match)
        if not url or url in seen:
            continue
        seen.add(url)
        evidence.append(LinkEvidence(url=url))
    return evidence


def _extract_timestamp_from_jsonld(soup: BeautifulSoup) -> Optional[str]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        value = _find_json_key(parsed, "datePublished")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_timestamp_from_time_tag(soup: BeautifulSoup) -> Optional[str]:
    time_tag = soup.find("time")
    if time_tag is None:
        return None
    if time_tag.get("datetime"):
        return str(time_tag["datetime"]).strip() or None
    value = time_tag.get_text(" ", strip=True)
    return value or None


def _find_json_key(value: Any, key: str) -> Optional[Any]:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_json_key(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_json_key(item, key)
            if found is not None:
                return found
    return None


def _confidence_reasons(
    text: str,
    html: Optional[str] = None,
    html_fragment: Optional[str] = None,
) -> list[str]:
    reasons: list[str] = []
    lowered_sources = " ".join(
        part.lower()
        for part in [text or "", html or "", html_fragment or ""]
        if isinstance(part, str)
    )

    if not text or len(text.strip()) < 12:
        reasons.append("Extracted text is too short or empty.")

    if any(marker in lowered_sources for marker in LOGIN_MARKERS):
        reasons.append("Page includes login/access-control indicators.")

    if any(marker in lowered_sources for marker in GENERIC_MARKERS) and len(text) < 80:
        reasons.append("Extracted content appears to be generic shell text.")

    return reasons


def _extract_author_from_title(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.match(r"^\s*([^:]+?)\s+on\s+(?:x|twitter)\s*:", value, flags=re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        return candidate or None
    return None


def _extract_handle(source: Optional[str]) -> Optional[str]:
    if not source:
        return None
    text = source.strip()
    if text.startswith("@"):
        handle = text[1:]
        return handle if handle else None
    parsed = urlparse(text)
    if parsed.netloc:
        path = parsed.path.strip("/")
        if path:
            return path.split("/")[0].lstrip("@") or None
    match = re.search(r"@([A-Za-z0-9_]{1,15})", text)
    if match:
        return match.group(1)
    return None


def _extract_handle_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 1:
        return parts[0].lstrip("@") or None
    return None


def _meta_content(soup: BeautifulSoup, selector: str) -> Optional[str]:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    value = tag.get("content")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    compact = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", compact).strip()


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_media_content_type(media_type: Optional[str]) -> Optional[str]:
    if media_type == "photo":
        return "image/*"
    if media_type in {"video", "animated_gif"}:
        return "video/*"
    return None


def _strip_trailing_punctuation(value: str) -> str:
    return value.rstrip(".,!?:;)]}")
