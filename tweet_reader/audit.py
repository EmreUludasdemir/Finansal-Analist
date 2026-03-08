from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import LinkEvidence, TweetData

CTA_MARKERS = [
    "get it here",
    "grab it here",
    "sign up",
    "register",
    "join",
    "download",
    "learn more",
    "become",
]

FACT_SIGNAL_RE = re.compile(r"\d|https?://", re.IGNORECASE)
INTERNAL_HOSTS = {"x.com", "twitter.com", "t.co", "pbs.twimg.com", "video.twimg.com", "pic.x.com"}


def build_evidence_audit(tweet: TweetData) -> dict[str, object]:
    checks = [
        _direct_access_check(tweet.link_evidence),
        _transparency_check(tweet.link_evidence),
        _verifiability_check(tweet),
        _intent_signal_check(tweet),
    ]

    verdict = _choose_verdict(checks, tweet.confidence)
    return {
        "verdict": verdict,
        "summary": _build_summary(verdict, checks),
        "checks": checks,
        "links": [_serialize_link(link) for link in tweet.link_evidence],
    }


def _direct_access_check(link_evidence: list[LinkEvidence]) -> dict[str, str]:
    if not link_evidence:
        return {
            "name": "direct_access",
            "status": "fail",
            "evidence": "The capture exposes no link metadata, so there is no direct source to open from the tweet itself.",
        }

    if any(_is_external_source(link) for link in link_evidence):
        return {
            "name": "direct_access",
            "status": "pass",
            "evidence": "At least one link resolves outside X/Twitter, so the referenced source can be opened directly.",
        }

    if all(_is_internal_only(link) for link in link_evidence):
        return {
            "name": "direct_access",
            "status": "fail",
            "evidence": "All detected links stay inside X/Twitter media or tweet pages; no external source document is exposed.",
        }

    return {
        "name": "direct_access",
        "status": "warn",
        "evidence": "Links were detected but could not be classified as direct external sources.",
    }


def _transparency_check(link_evidence: list[LinkEvidence]) -> dict[str, str]:
    if not link_evidence:
        return {
            "name": "transparency",
            "status": "fail",
            "evidence": "There are no expanded or resolved URLs to inspect.",
        }

    unresolved_shorteners = [
        link for link in link_evidence if _is_shortener(link.url) and not (link.expanded_url or link.resolved_url)
    ]
    if unresolved_shorteners:
        return {
            "name": "transparency",
            "status": "warn",
            "evidence": "Some shortened URLs could not be expanded or resolved, so the true destination is still opaque.",
        }

    if any(_is_external_source(link) for link in link_evidence):
        return {
            "name": "transparency",
            "status": "pass",
            "evidence": "Expanded or resolved URLs reveal where the tweet sends readers.",
        }

    return {
        "name": "transparency",
        "status": "fail",
        "evidence": "Resolved links point only to tweet media or internal pages instead of a named external source.",
    }


def _verifiability_check(tweet: TweetData) -> dict[str, str]:
    claim_like = bool(tweet.text.strip()) and bool(FACT_SIGNAL_RE.search(tweet.text))
    if any(_is_external_source(link) for link in tweet.link_evidence):
        return {
            "name": "verifiability",
            "status": "pass",
            "evidence": "The tweet exposes an external resource that can be checked against the claims.",
        }

    if claim_like:
        return {
            "name": "verifiability",
            "status": "fail",
            "evidence": "The tweet contains claim-like text but does not expose a direct external source for verification.",
        }

    return {
        "name": "verifiability",
        "status": "warn",
        "evidence": "There is not enough structured claim or source data to verify the tweet automatically.",
    }


def _intent_signal_check(tweet: TweetData) -> dict[str, str]:
    lowered = tweet.text.lower()
    matched_markers = [marker for marker in CTA_MARKERS if marker in lowered]
    if matched_markers:
        detail = ", ".join(sorted(set(matched_markers)))
        return {
            "name": "intent_signal",
            "status": "warn",
            "evidence": f"CTA language detected ({detail}), which often indicates promotion or funnel behavior rather than transparent sourcing.",
        }

    return {
        "name": "intent_signal",
        "status": "pass",
        "evidence": "No obvious promotional CTA language was detected in the captured text.",
    }


def _choose_verdict(checks: list[dict[str, str]], confidence: str) -> str:
    statuses = {check["name"]: check["status"] for check in checks}
    fail_count = sum(1 for check in checks if check["status"] == "fail")
    warn_count = sum(1 for check in checks if check["status"] == "warn")

    if statuses.get("direct_access") == "fail" and statuses.get("verifiability") == "fail":
        return "red"
    if fail_count >= 2:
        return "red"
    if confidence == "low" or fail_count == 1 or warn_count:
        return "yellow"
    return "green"


def _build_summary(verdict: str, checks: list[dict[str, str]]) -> str:
    by_name = {check["name"]: check for check in checks}
    if verdict == "red":
        return (
            f"{by_name['direct_access']['evidence']} "
            f"{by_name['verifiability']['evidence']}"
        )
    if verdict == "yellow":
        return "The tweet is only partially auditable from public metadata and should be reviewed manually before reuse."
    return "The tweet exposes enough public evidence to support a basic verification workflow."


def _serialize_link(link: LinkEvidence) -> dict[str, object]:
    return {
        "url": link.url,
        "expanded_url": link.expanded_url,
        "display_url": link.display_url,
        "resolved_url": link.resolved_url,
        "content_type": link.content_type,
        "kind": link.kind,
        "resolution_error": link.resolution_error,
    }


def _is_external_source(link: LinkEvidence) -> bool:
    target = (link.resolved_url or link.expanded_url or link.url or "").strip()
    if not target:
        return False

    parsed = urlparse(target)
    host = parsed.netloc.lower()
    if not host:
        return False
    return all(host != internal and not host.endswith(f".{internal}") for internal in INTERNAL_HOSTS)


def _is_internal_only(link: LinkEvidence) -> bool:
    target = (link.resolved_url or link.expanded_url or link.url or "").strip()
    if not target:
        return False
    parsed = urlparse(target)
    host = parsed.netloc.lower()
    if not host:
        return False
    return any(host == internal or host.endswith(f".{internal}") for internal in INTERNAL_HOSTS)


def _is_shortener(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "t.co"
