# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-06-01

### Fixed
- Pinned the build backend to a PyPI-publish-compatible Hatchling release after the first `v0.1.5` publish attempt produced wheel metadata rejected by the publish action.

## [0.1.5] - 2026-06-01

### Fixed
- `young flow` now always shows the latest verified A-share fund-flow record when available, even if the source trading date differs from the requested report date.
- Old cached "fund flow unavailable" responses are ignored so upgrades do not keep showing stale empty output.
- If the realtime fund-flow interface is temporarily unavailable, `young flow` now tries an online market fund-flow snapshot endpoint before falling back to the most recent locally cached good record.
- When Eastmoney realtime fund-flow endpoints are unavailable, `young flow` now tries additional no-login online market indicators from Sina/Tencent before using the last known good local fund-flow cache; indicator fallbacks are clearly labeled and are not presented as main-capital net inflow.

### Changed
- Data-source diagnostic traces are quiet by default; set `YOUNG_STOCK_DEBUG=1` to show them while troubleshooting.
- Added `--no-news` to market commands that can print news links (`young hk`, `young us`) to match the existing single-stock `--no-news` option.
- Market commands now print the current session stage (morning, midday, afternoon, or after-hours), and stale/latest-available data is labeled as the returned trading date's after-hours data.
- News lookup now aggregates multiple no-login sources (Futu, Sina Finance, Eastmoney fast news) and uses filtered news heat to rank HK/US focus stocks Top 5.

## [0.1.4] - 2026-06-01

### Fixed
- `young flow` now returns the latest verified A-share fund-flow record instead of going blank when the requested date is newer than the data source.
- Default trade-date selection now keeps pre-close weekday runs on the previous trading day, avoiding premature same-day reports before A-share data settles.

### Added
- Added `young stock <symbol>` for single-stock snapshots across A-share, Hong Kong, and best-effort US symbols, with source/date labels and optional news lookup.

### Changed
- Fund-flow output is explicitly labeled as A-share / Shanghai Composite scope and prints the returned trading date.
- A-share reports only use fund-flow data when the returned trading date matches the report date; stale source data is shown as a clear notice rather than mixed into the review.
- Documentation no longer describes Eastmoney `push2his` as a stable historical fund-flow fallback.

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
