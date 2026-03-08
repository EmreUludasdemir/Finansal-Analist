from __future__ import annotations

import re
from urllib.parse import urlparse

from .audit import build_evidence_audit
from .models import TweetData

ASSUMPTION_MARKERS = [
    "i think",
    "maybe",
    "probably",
    "likely",
    "might",
    "could",
    "should",
    "i believe",
    "i feel",
    "seems",
]

MONTH_WORDS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def build_summary(tweet: TweetData) -> dict[str, object]:
    claims = _key_claims(tweet.text, max_claims=3)
    verifiable, assumptions = _classify_claims(claims)
    evidence_audit = build_evidence_audit(tweet)
    checks = _suggested_checks(tweet)

    return {
        "capture_metadata": {
            "tweet_id": tweet.tweet_id,
            "source": tweet.source,
            "captured_at_utc": tweet.captured_at_utc,
            "confidence": tweet.confidence,
            "confidence_reasons": tweet.confidence_reasons,
        },
        "key_claims": claims,
        "what_is_verifiable_vs_assumption": {
            "verifiable": verifiable,
            "assumptions_or_interpretations": assumptions,
        },
        "evidence_audit": evidence_audit,
        "suggested_checks": checks,
    }


def _key_claims(text: str, max_claims: int) -> list[str]:
    if not text.strip():
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    sentence_candidates: list[str] = []
    for chunk in normalized.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        sentence_candidates.extend(_split_sentences(chunk))

    claims = []
    for candidate in sentence_candidates:
        clean = candidate.strip()
        if len(clean) < 15:
            continue
        claims.append(clean)
        if len(claims) >= max_claims:
            break
    return claims


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _classify_claims(claims: list[str]) -> tuple[list[str], list[str]]:
    verifiable: list[str] = []
    assumptions: list[str] = []

    for claim in claims:
        lower = claim.lower()
        if any(marker in lower for marker in ASSUMPTION_MARKERS):
            assumptions.append(claim)
            continue

        has_fact_signal = bool(
            re.search(r"\d", claim)
            or any(month in lower for month in MONTH_WORDS)
            or re.search(r"https?://", claim)
            or re.search(r"\b(?:announced|reported|launched|released|confirmed|stated)\b", lower)
        )
        if has_fact_signal:
            verifiable.append(claim)
        else:
            assumptions.append(claim)

    if not verifiable and claims:
        verifiable = [claims[0]]
        assumptions = [item for item in claims[1:] if item not in verifiable]

    return verifiable, assumptions


def _suggested_checks(tweet: TweetData) -> list[str]:
    checks = [
        "Open the original tweet URL and verify the extracted text matches exactly.",
    ]

    if not tweet.author_handle:
        checks.append("Verify the author handle manually from the tweet page.")
    else:
        checks.append("Confirm the captured handle matches the profile shown on the tweet.")

    if not tweet.timestamp:
        checks.append("Check and record the tweet timestamp manually.")
    else:
        checks.append("Confirm the timestamp and timezone as shown in the original tweet.")

    if tweet.thread_items:
        checks.append("Verify that all thread items are present and in order.")
    else:
        checks.append("If this is part of a thread, verify that replies/continuations were not missed.")

    if tweet.confidence == "low":
        checks.append("Content may be incomplete; consider using manual paste mode for a full capture.")

    if re.search(r"https?://", tweet.text):
        checks.append("Open linked URLs from the tweet and verify referenced claims.")

    if tweet.link_evidence:
        checks.append("Review resolved link targets and confirm they match what the tweet promises.")

    if any(link.kind == "media" for link in tweet.link_evidence) and not any(
        link.kind == "external" or _looks_external_target(link.resolved_url)
        for link in tweet.link_evidence
    ):
        checks.append("Treat media-only links as unverified until you locate a direct external source.")

    deduped: list[str] = []
    seen = set()
    for check in checks:
        if check not in seen:
            deduped.append(check)
            seen.add(check)
    return deduped


def _looks_external_target(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    internal_hosts = ("x.com", "twitter.com", "t.co", "pbs.twimg.com", "video.twimg.com", "pic.x.com")
    return all(host != internal and not host.endswith(f".{internal}") for internal in internal_hosts)
