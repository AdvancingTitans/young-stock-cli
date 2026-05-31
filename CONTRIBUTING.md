# Contributing

Thanks for your interest in improving `young-stock-cli`. This is a small,
focused project; contributions of all sizes are welcome.

## Development setup

```bash
git clone https://github.com/AdvancingTitans/young-stock-cli.git
cd young-stock-cli
uv venv --python 3.11
uv pip install -e ".[dev]"
uv run pytest -q
```

## How to contribute

- **Bug reports**: open an issue with the exact command you ran, the full
  stack trace, and the trading day you queried (Eastmoney's payload format
  changes over time — knowing the date matters).
- **New data source / endpoint**: open an issue first to discuss API
  stability and rate-limit behaviour before sending a PR.
- **Documentation / translation**: PRs welcome. The README is bilingual
  (English on top, Chinese below).

## Pull request checklist

- [ ] `uv run pytest -q` passes locally.
- [ ] `uv run ruff check src tests` is clean.
- [ ] New behaviour has a test (mock the network, do not hit live APIs).
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.

## Code style

- Python 3.8+ syntax (we still support 3.8 because some quant users are
  stuck on legacy interpreters).
- 100-column line limit (enforced by ruff).
- Prefer the standard library; runtime dependencies should stay at zero
  unless there's a clear reason.

## Release process

Maintainers only:

1. Bump `__version__` in `src/young_stock_cli/__version__.py`.
2. Move `## [Unreleased]` content to a new dated section in `CHANGELOG.md`.
3. Tag: `git tag v0.x.y && git push --tags`.
4. GitHub Actions builds the wheel and publishes to PyPI on tag push.
