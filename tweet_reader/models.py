from dataclasses import dataclass, field
from typing import List, Literal, Optional

ConfidenceLevel = Literal["high", "low"]
LinkKind = Literal["external", "media", "unknown"]


@dataclass
class LinkEvidence:
    url: str
    expanded_url: Optional[str] = None
    display_url: Optional[str] = None
    resolved_url: Optional[str] = None
    content_type: Optional[str] = None
    kind: LinkKind = "unknown"
    resolution_error: Optional[str] = None


@dataclass
class TweetData:
    url: str
    tweet_id: Optional[str] = None
    captured_at_utc: Optional[str] = None
    author_name: Optional[str] = None
    author_handle: Optional[str] = None
    timestamp: Optional[str] = None
    text: str = ""
    thread_items: List[str] = field(default_factory=list)
    confidence: ConfidenceLevel = "high"
    confidence_reasons: List[str] = field(default_factory=list)
    source: str = "unknown"
    link_evidence: List[LinkEvidence] = field(default_factory=list)
