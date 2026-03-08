# Share Copy

## GitHub repo description

Public tweet evidence audit CLI for X/Twitter posts. Captures public metadata, resolves links, and produces reproducible red/yellow/green verification reports.

## GitHub pinned project blurb

Built a Python CLI that turns public X/Twitter posts into evidence audits. It captures accessible tweet metadata, resolves link targets, classifies claims vs assumptions, and emits structured markdown/JSON reports with a red/yellow/green verdict.

## LinkedIn post draft

I built a small Python CLI for auditing public X/Twitter posts.

The goal is simple: do not treat screenshots or viral claims as evidence by default.

This tool:

- captures public tweet metadata without login when possible
- preserves raw payloads for reproducibility
- resolves shortened links
- distinguishes claim text from verifiable source evidence
- outputs a red/yellow/green audit verdict in markdown and JSON

I used it on a real post that claimed to link to a PDF and the tool showed the tweet only resolved to internal media, not to an external source document.

Repo focus:

- Python CLI design
- parsing and normalization
- public web retrieval fallbacks
- evidence-based risk checks
- deterministic tests with fixtures

## CV bullet

Built a Python CLI that audits public X/Twitter posts by capturing public metadata, resolving shortened links, and generating reproducible evidence reports with automated red/yellow/green credibility checks.
