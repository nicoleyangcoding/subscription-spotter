# Contributing

Thanks for helping. Small pull requests are easiest to review.

## Never share real financial data

When reporting a CSV format that isn't detected, share only the header row and one or two **made-up** rows in the same format. Don't attach real statements to issues or pull requests.

## Development setup

```bash
git clone https://github.com/nicoleyangcoding/subscription-spotter
cd subscription-spotter
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```

`examples/make_sample.py` regenerates the sample statement. All merchant names in it are fictional.

## Guidelines

- No runtime dependencies and no network access.
- Use `Decimal` for money, never floats.
- When a detection rule changes, add a test with a small made-up transaction list.
