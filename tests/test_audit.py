import unittest

from tweet_reader.audit import build_evidence_audit
from tweet_reader.models import LinkEvidence, TweetData


class AuditTests(unittest.TestCase):
    def test_build_evidence_audit_green_when_external_source_is_exposed(self) -> None:
        tweet = TweetData(
            url="https://x.com/example/status/1",
            text="Read the paper here: https://example.org/paper.pdf",
            confidence="high",
            link_evidence=[
                LinkEvidence(
                    url="https://example.org/paper.pdf",
                    resolved_url="https://example.org/paper.pdf",
                    content_type="application/pdf",
                    kind="external",
                )
            ],
        )

        audit = build_evidence_audit(tweet)

        self.assertEqual(audit["verdict"], "green")

    def test_build_evidence_audit_yellow_when_external_source_exists_but_capture_is_low_confidence(self) -> None:
        tweet = TweetData(
            url="https://x.com/example/status/2",
            text="Possibly relevant source: https://example.org/report",
            confidence="low",
            confidence_reasons=["Page includes login/access-control indicators."],
            link_evidence=[
                LinkEvidence(
                    url="https://t.co/example",
                    expanded_url="https://example.org/report",
                    resolved_url="https://example.org/report",
                    content_type="text/html",
                    kind="external",
                )
            ],
        )

        audit = build_evidence_audit(tweet)

        self.assertEqual(audit["verdict"], "yellow")


if __name__ == "__main__":
    unittest.main()
