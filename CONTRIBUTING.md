# Contributing

Thanks for considering a contribution! This project welcomes pull requests, bug reports, and feature suggestions.

## Quick start

```bash
git clone https://github.com/AdvancingTitans/young-stock-cli.git
cd young-stock-cli
pip install -e ".[dev]"
pytest
ruff check .
```

## Pull requests

1. Fork → create a topic branch (`feat/...` or `fix/...`).
2. Add or update tests for your change.
3. Run `pytest` and `ruff check .` locally — CI runs both.
4. Open a PR with a clear description: what + why.

## Reporting bugs

Please include:

- `young --version`
- Python version (`python --version`)
- OS
- The exact command you ran and the full traceback / output.

## Code style

- `ruff` for linting and import sorting.
- Type hints encouraged but not required for small fixes.
- Keep functions focused; prefer composing small helpers.

## License

By contributing, you agree your contribution will be licensed under the MIT license.
