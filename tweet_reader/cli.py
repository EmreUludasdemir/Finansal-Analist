from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Optional

from .fetch import enrich_link_evidence, fetch_html, fetch_oembed, fetch_syndication
from .models import TweetData
from .parse import parse_html, parse_manual_paste, parse_oembed, parse_syndication, validate_tweet_url
from .render import render_markdown
from .summarize import build_summary

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
MANUAL_PASTE_PATH = DATA_DIR / "tweet_paste.txt"
RAW_JSON_PATH = DATA_DIR / "tweet_raw.json"
RAW_HTML_PATH = DATA_DIR / "tweet_raw.html"
MARKDOWN_PATH = OUTPUT_DIR / "tweet.md"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        _print_usage()
        return 2

    tweet_url = args[0].strip()
    if not validate_tweet_url(tweet_url):
        print("Invalid tweet URL. Use a public x.com/twitter.com status URL.")
        _print_usage()
        return 2

    _ensure_dirs()

    try:
        tweet = None

        syndication_payload, syndication_error = fetch_syndication(tweet_url)
        if syndication_payload is not None:
            _write_raw_json(syndication_payload)
            tweet = parse_syndication(tweet_url, syndication_payload)
        else:
            oembed_payload, oembed_error = fetch_oembed(tweet_url)
            if oembed_payload is not None:
                _write_raw_json(oembed_payload)
                tweet = parse_oembed(tweet_url, oembed_payload)
            else:
                html, html_error = fetch_html(tweet_url)
                if html is not None:
                    _write_raw_html(html)
                    tweet = parse_html(tweet_url, html)
                else:
                    print("Public retrieval failed.")
                    if syndication_error:
                        print(f"- Strategy A (syndication): {syndication_error}")
                    if oembed_error:
                        print(f"- Strategy B (oEmbed): {oembed_error}")
                    if html_error:
                        print(f"- Strategy C (HTML): {html_error}")

        if tweet is None or tweet.confidence == "low" or not tweet.text.strip():
            if tweet is not None and tweet.confidence == "low":
                print("Public retrieval appears incomplete (low confidence).")
                if tweet.confidence_reasons:
                    for reason in tweet.confidence_reasons:
                        print(f"- {reason}")

            manual_tweet = _try_manual_mode(tweet_url)
            if manual_tweet is None:
                return 3
            tweet = manual_tweet

        tweet.captured_at_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        tweet.link_evidence = enrich_link_evidence(tweet.link_evidence)
        summary = build_summary(tweet)
        render_markdown(tweet, summary, MARKDOWN_PATH)
        SUMMARY_PATH.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"Saved markdown: {MARKDOWN_PATH}")
        print(f"Saved summary: {SUMMARY_PATH}")
        if RAW_JSON_PATH.exists():
            print(f"Saved raw capture: {RAW_JSON_PATH}")
        elif RAW_HTML_PATH.exists():
            print(f"Saved raw capture: {RAW_HTML_PATH}")

        return 0
    except Exception as exc:  # pragma: no cover - defensive final catch
        print(f"Unexpected error: {exc}")
        return 4


def _try_manual_mode(tweet_url: str) -> Optional[TweetData]:
    if MANUAL_PASTE_PATH.exists():
        raw_text = MANUAL_PASTE_PATH.read_text(encoding="utf-8")
        if raw_text.strip():
            print(f"Using manual paste content from {MANUAL_PASTE_PATH}")
            return parse_manual_paste(tweet_url, raw_text)

    _print_manual_instructions(tweet_url)
    return None


def _print_usage() -> None:
    print('Usage: python -m tweet_reader "<TWEET_URL>"')


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _write_raw_json(payload: dict) -> None:
    RAW_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if RAW_HTML_PATH.exists():
        RAW_HTML_PATH.unlink()


def _write_raw_html(html: str) -> None:
    RAW_HTML_PATH.write_text(html, encoding="utf-8")
    if RAW_JSON_PATH.exists():
        RAW_JSON_PATH.unlink()


def _print_manual_instructions(tweet_url: str) -> None:
    print("Manual capture required.")
    print(f"1. Paste tweet/thread text into: {MANUAL_PASTE_PATH}")
    print("2. Optional metadata lines at top of the file:")
    print("   Author: <display name>")
    print("   Handle: @<username>")
    print("   Timestamp: <timestamp text>")
    print(f'3. Rerun: python -m tweet_reader "{tweet_url}"')
