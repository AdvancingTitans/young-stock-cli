# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-05-31

### Added
- Added Tencent Finance as an additional no-login quote fallback, with Hong Kong indices using Tencent's close-oriented quote first.
- Added a news fallback chain: Futu news, Futu feed, then Sina Finance rolling news.

### Changed
- Market reports now show friendlier source/quality notes, explicit fund-flow source, and a less technical footer.
- Global/HK index tables distinguish turnover from volume and show the active data source.

## [0.1.2] - 2026-05-31

### Fixed
- `young flow` now falls back to Eastmoney's historical fund-flow endpoint and a broader request strategy when the realtime endpoint closes Python direct connections.
- `young hk` now uses Sina's full `hkHSI` quote for Hang Seng Index volume instead of the volume-less `int_hangseng` quote.

## [0.1.1] - 2026-05-31

### Added
- `young update` — upgrade the installed CLI from the current Python environment.

### Changed
- Synced the CLI implementation with the latest stock-analysis quote source fixes.

## [0.1.0] - 2026-05-31

### Added
- Initial public release.
- `young a` — A-share after-hours dashboard (indices, ZT/DT pool, fund flow, sector boards).
- `young hk`, `young us`, `young global` — Hong Kong / US / global indices snapshots.
- `young indices`, `young zt-pool`, `young flow` — focused subcommands.
- `young cache-clear` — manage the local response cache.
- Eastmoney public endpoints (`push2.eastmoney.com`, `push2ex.eastmoney.com`) integrated, no login required.
- Built-in 7-day response cache (`~/.young_stock/cache/`).
- Rich terminal tables for human-friendly output.
