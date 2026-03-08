import json
import unittest
from pathlib import Path

from tweet_reader.parse import parse_html, parse_oembed, parse_syndication
from tweet_reader.summarize import build_summary

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_parse_oembed_extracts_author_timestamp_and_thread(self) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_tweet_oembed.json").read_text(encoding="utf-8"))
        tweet = parse_oembed("https://x.com/janedoe/status/1234567890123456789", payload)

        self.assertEqual(tweet.author_name, "Jane Doe")
        self.assertEqual(tweet.author_handle, "janedoe")
        self.assertEqual(tweet.timestamp, "January 1, 2026")
        self.assertIn("1/ Launching feature X today.", tweet.text)
        self.assertEqual(len(tweet.thread_items), 3)
        self.assertEqual(tweet.thread_items[1], "2/ We reduced latency by 35%.")
        self.assertEqual(tweet.confidence, "high")

    def test_parse_html_marks_low_confidence_for_login_wall(self) -> None:
        html = (FIXTURES_DIR / "sample_tweet_html.html").read_text(encoding="utf-8")
        tweet = parse_html("https://x.com/janedoe/status/1234567890123456789", html)

        self.assertEqual(tweet.author_name, "Jane Doe")
        self.assertEqual(tweet.author_handle, "janedoe")
        self.assertEqual(tweet.confidence, "low")
        self.assertTrue(
            any("login" in reason.lower() or "access-control" in reason.lower() for reason in tweet.confidence_reasons)
        )
        self.assertTrue("log in" in tweet.text.lower() or "requires login" in tweet.text.lower())

    def test_parse_syndication_extracts_media_link_evidence(self) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_tweet_syndication.json").read_text(encoding="utf-8"))
        tweet = parse_syndication("https://x.com/quantscience_/status/2023750362184724759", payload)

        self.assertEqual(tweet.author_name, "Quant Science")
        self.assertEqual(tweet.author_handle, "quantscience_")
        self.assertEqual(tweet.timestamp, "2026-02-17T13:24:20.000Z")
        self.assertEqual(tweet.tweet_id, "2023750362184724759")
        self.assertEqual(len(tweet.link_evidence), 1)
        self.assertEqual(tweet.link_evidence[0].kind, "media")
        self.assertEqual(tweet.link_evidence[0].resolved_url, "https://pbs.twimg.com/media/HBXOOn7bAAAgFN4.png")

    def test_build_summary_flags_media_only_claim_as_red(self) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_tweet_syndication.json").read_text(encoding="utf-8"))
        tweet = parse_syndication("https://x.com/quantscience_/status/2023750362184724759", payload)

        summary = build_summary(tweet)
        audit = summary["evidence_audit"]

        self.assertEqual(audit["verdict"], "red")
        direct_access = next(check for check in audit["checks"] if check["name"] == "direct_access")
        self.assertEqual(direct_access["status"], "fail")
        self.assertIn("no external source document", direct_access["evidence"].lower())


if __name__ == "__main__":
    unittest.main()
