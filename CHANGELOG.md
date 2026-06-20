# Changelog

## [0.3.0] - 2026-06-21

### Added

- A clearer product surface for market snapshots, stock evidence, fund flow, LHB, watchlists, and report export.
- Fifteen investor lenses plus the shared `young style` / `/style` registry, including the hidden `--lens all` multi-lens debate path.
- A single deep replay framework for `young daily --llm` and `young analyze <symbol>`, with M1–M7 structure and method cards.
- Persistent local state for `profile`, `portfolio`, `memory`, `diary`, and model/channel configuration.

### Changed

- `young daily` stays deterministic by default; `--llm` is the explicit deep replay path.
- `young report` remains PDF export only, and `young send` only attaches the matching PDF when it exists.
- Browser use stays opt-in with `--browser-fallback`, and richer supplemental sources stay opt-in with `--rich-source`.
- Model settings are centralized in `young config models`, with masked display and chat-style migration behavior.

### Fixed

- Secrets are masked in config and diagnostic output.
- Saved chat style and analysis framework values stay synchronized.
- Report identities, PDF export, and delivery paths follow the same date/session/topic contract.
- Default output keeps missing evidence missing instead of turning gaps into invented numbers.
