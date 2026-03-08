# Contributing

## Local setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Development workflow

1. Add or update fixtures in `tests/fixtures/` for deterministic coverage.
2. Run unit tests before committing.
3. If you change report shape, refresh the checked-in examples.
4. Keep the tool public-web only. Do not add login bypass or scraping behavior that depends on private sessions.

## Commands

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m tweet_reader "https://x.com/<handle>/status/<id>"
```

## Design constraints

- Prefer deterministic fixtures over network-heavy tests.
- Keep evidence checks explainable. A verdict should always be traceable to concrete link or text evidence.
- Preserve raw captures when public retrieval succeeds.
- Treat missing or partial data as a confidence problem, not as silent success.
