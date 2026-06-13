# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.17] - 2026-06-14

### Fixed
- Lowered package metadata to Python 3.9+ after verifying the source compiles on Python 3.9, so macOS system `pip3 install young-stock-cli` no longer rejects every release as Python 3.10-only.
- `young update` now prints a concrete Python-version and `python3 -m pip` retry hint when pip fails.
- Removed Python 3.10-only `zip(strict=False)` calls so fund-flow parsing works under Python 3.9.

### Changed
- Install docs now prefer `python3 -m pip install young-stock-cli` and CI covers Python 3.9.
- `young diagnose --json` now prints read-only machine-readable support diagnostics, and tests cover every top-level command's `--help`.

## [0.1.16] - 2026-06-04

### Changed
- `young profile add-stock/add-fund` now requires `--buy-date` and `--quantity`, validates symbols/fund codes before writing memory, and confirms the resolved security name/code in Chinese.
- Personalized daily reports now show only markets relevant to the user's direct stock holdings and fund top-10 holdings instead of defaulting to a global market section.
- Fund and stock advice now varies by buy-date return, same-day move, and available news signal instead of repeating the same holding sentence.

## [0.1.15] - 2026-06-04

### Added
- Added optional position memory on `young profile add-stock/add-fund` through `--buy-date` and `--quantity`; reports automatically look up the buy-date stock close or fund NAV instead of asking users to enter cost price.
- Added personalized fund-only, stock-only, and combined portfolio analysis in daily reports, including estimated return since purchase, news trend, holding stance, and portfolio concentration guidance.

### Changed
- Reworked daily advice from generic framework language into separate `基金分析`, `个股分析`, and `综合持仓` sections.

## [0.1.14] - 2026-06-03

### Added
- Added `young uninstall` to remove the package from the current Python environment with one command.
- Added `young profile clear-stocks` and `young profile clear-funds` for one-click stock/fund memory cleanup without deleting the other side.

### Changed
- Daily report summary/key-points/full modes now tie risk notes to the user's watched symbols, fund estimates, and available news instead of printing generic caution text.

## [0.1.13] - 2026-06-03

### Added
- Added `young daily --format summary|key-points|full`, plus `--only`, `--order`, and `--quick` for shorter daily reports and configurable report sections.
- Added profile management commands: `young profile list`, `remove-stock`, `remove-fund`, `clear`, and `profile group create/add`.
- Added local productivity commands for staged workflows: `young portfolio`, `young alert`, `young note`, and `young diary`.
- Added `young diagnose`, `young guide`, and `young example` for friendlier troubleshooting and onboarding.

### Changed
- Fund holding reports now show the holding as-of date age and warn when stale quarterly holdings may have changed.
- Daily report summary/key-points modes avoid long news and full market sections by default.

## [0.1.12] - 2026-06-03

### Added
- Added `young profile add-stock`, `young profile add-fund`, and `young profile show` to maintain local investment memory in `~/.young_stock/profile.json`.
- Added `young daily`, a personalized daily market report that combines saved stock/fund watchlists, global indices, A-share sentiment, fund flow, and risk-oriented suggestions.
- Exposed `run_daily_report()` in `young_stock._core` so agent skills can depend on the PyPI package instead of copying the core script.
- Added focused `calendar`, `profile`, `reports`, and `health` modules as the first step of the v2 architecture split.
- Added an explicit 2026 market-calendar layer for A-share, HK, and US holiday-aware nearest-trade-day resolution.
- Added lightweight data-source health snapshots that track recent success rate and latency for public quote/news APIs.

### Changed
- The daily report uses the existing nearest-trade-date logic, so pre-close weekday runs still review the latest settled trading day.
- CLI investment-memory logic moved out of `cli.py`; `_core.run_daily_report()` and `_core.nearest_trade_date()` remain compatibility wrappers over the new modules.

## [0.1.11] - 2026-06-02

### Fixed
- Tonghuashun concept fund-flow is used only when both net-inflow and net-outflow rankings are available; otherwise `young flow` falls back to the existing Eastmoney/Sina/Tencent/local-cache chain.
- Fund-flow headings now match the actual source scope, including concept boards, sector boards, market-activity references, and Eastmoney main-capital flow.

### Changed
- Normal command output no longer prints engineering-style data-quality/completeness/source-diagnostic sections; detailed diagnostics remain available with `YOUNG_STOCK_DEBUG=1`.

## [0.1.10] - 2026-06-02

### Added
- `young flow` now tries the Tonghuashun concept fund-flow page first and displays top concept net inflow/outflow directions when available.

### Changed
- Fund-flow output now adapts its title to the active source scope: concept board, sector board, market activity, or Eastmoney main-capital flow.
- Tonghuashun concept flow is treated as a board-direction reference and is clearly labeled as not equivalent to whole-market main-capital net inflow.

## [0.1.9] - 2026-06-01

### Added
- Added `young fund <code>` for fund-focused users. It shows the fund's same-day estimated return, latest NAV date, top A-share holdings, holding-stock quotes, rough holding contribution, and same-day holding-stock news.
- `young flow` now has an additional Sina Finance sector fund-flow page fallback before falling back to Sina/Tencent market-activity references and the last known good local cache.

### Changed
- News aggregation now filters out links that clearly point to empty/404/no-content pages and replaces them with other same-day items when available.
- Fund news is ranked across the fund's top holdings by same-day multi-source heat, with `--no-news` available for quote-only output.

## [0.1.8] - 2026-06-01

### Fixed
- Focused commands now include clearer market/date context, including `YYYY-MM-DD + stage` labels such as `2026-05-29 交易日盘后`.
- A-share activity fallback no longer pretends the requested date is the data date when the online source has no explicit trading date.

### Changed
- All news displays now filter to the requested trading date only, show at most five items, show fewer when fewer valid items exist, and print a clear empty-state message when no effective news is found.
- `young a` now includes an A-share news section by default and supports `--no-news`.
- News heat ranking now omits zero-news symbols instead of filling Top 5 with inactive tickers.

## [0.1.7] - 2026-06-01

### Added
- Added `young news <symbol>` for a quick single-stock news/momentum check without printing the full quote report.

### Changed
- News output now shows the source and link status on every item, including a clear "no public link" label instead of blank lines.
- Multi-source news ranking now keeps per-source hit counts and uses a source-balanced display so Futu does not automatically crowd out Sina Finance or Eastmoney items when those sources have matching news.
- Hong Kong stock news aliases now strip suffixes such as `-W` / `－Ｗ`, improving matches for names like Meituan-W.

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
