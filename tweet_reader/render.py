from __future__ import annotations

from pathlib import Path

from .models import TweetData


def render_markdown(tweet: TweetData, summary: dict[str, object], output_path: Path) -> None:
    title = _build_title(tweet)
    lines: list[str] = [
        "# Tweet Evidence Audit",
        "",
        "## Title",
        title,
        "",
        "## URL",
        tweet.url,
        "",
    ]

    if tweet.author_name or tweet.author_handle:
        lines.extend(
            [
                "## Author",
                _format_author(tweet.author_name, tweet.author_handle),
                "",
            ]
        )

    if tweet.timestamp:
        lines.extend(
            [
                "## Timestamp",
                tweet.timestamp,
                "",
            ]
        )

    if tweet.tweet_id or tweet.captured_at_utc or tweet.source:
        lines.append("## Capture Metadata")
        if tweet.tweet_id:
            lines.append(f"- Tweet ID: {tweet.tweet_id}")
        if tweet.source:
            lines.append(f"- Source: {tweet.source}")
        if tweet.captured_at_utc:
            lines.append(f"- Captured At (UTC): {tweet.captured_at_utc}")
        lines.append("")

    lines.extend(
        [
            "## Extracted Text",
            "```text",
            tweet.text or "(No text extracted)",
            "```",
            "",
        ]
    )

    if tweet.thread_items:
        lines.append("## Thread Items")
        lines.extend(f"{index}. {item}" for index, item in enumerate(tweet.thread_items, start=1))
        lines.append("")

    evidence_audit = summary.get("evidence_audit")
    if isinstance(evidence_audit, dict):
        lines.extend(
            [
                "## Evidence Audit",
                f"Verdict: {str(evidence_audit.get('verdict', 'unknown')).upper()}",
                "",
                str(evidence_audit.get("summary", "")).strip() or "No audit summary available.",
                "",
            ]
        )

        checks = evidence_audit.get("checks")
        if isinstance(checks, list) and checks:
            lines.append("### Checks")
            for check in checks:
                if not isinstance(check, dict):
                    continue
                name = str(check.get("name", "unknown")).replace("_", " ").title()
                status = str(check.get("status", "unknown")).upper()
                evidence = str(check.get("evidence", "")).strip()
                lines.append(f"- {name} [{status}]: {evidence}")
            lines.append("")

        link_rows = evidence_audit.get("links")
        if isinstance(link_rows, list) and link_rows:
            lines.append("### Link Evidence")
            for item in link_rows:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "- "
                    + _format_link_row(
                        url=str(item.get("url", "")).strip(),
                        expanded_url=str(item.get("expanded_url", "")).strip() or None,
                        resolved_url=str(item.get("resolved_url", "")).strip() or None,
                        kind=str(item.get("kind", "")).strip() or None,
                        content_type=str(item.get("content_type", "")).strip() or None,
                    )
                )
            lines.append("")

    if tweet.confidence == "low":
        lines.append("## Possible Missing Content")
        if tweet.confidence_reasons:
            lines.extend(f"- {reason}" for reason in tweet.confidence_reasons)
        else:
            lines.append("- Public retrieval appears incomplete.")
        lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _build_title(tweet: TweetData) -> str:
    if tweet.author_handle:
        return f"Tweet by @{tweet.author_handle}"
    if tweet.author_name:
        return f"Tweet by {tweet.author_name}"
    return "Tweet Capture"


def _format_author(name: str | None, handle: str | None) -> str:
    if name and handle:
        return f"{name} (@{handle})"
    if handle:
        return f"@{handle}"
    return name or "Unknown"


def _format_link_row(
    url: str,
    expanded_url: str | None,
    resolved_url: str | None,
    kind: str | None,
    content_type: str | None,
) -> str:
    parts = [f"source={url}"]
    if expanded_url:
        parts.append(f"expanded={expanded_url}")
    if resolved_url:
        parts.append(f"resolved={resolved_url}")
    if kind:
        parts.append(f"kind={kind}")
    if content_type:
        parts.append(f"content_type={content_type}")
    return " | ".join(parts)
