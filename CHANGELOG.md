# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.11] - 2026-06-20

### Changed

- Removed the deprecated `young replay` compatibility command so `young daily --llm` is now the only LLM deep-replay entry.
- Tightened the chat slash-command surface by removing the old `/replay` and `/daily-llm` compatibility aliases.
- Clarified throughout the CLI help and README that plain `young daily` is deterministic and does not require any LLM configuration.
- Updated `young send` docs to match the current delivery contract: send the latest Markdown plus summary first, and attach the same-name PDF only when it exists.

### Fixed

- Added regression coverage to keep deterministic `young daily` on the non-LLM path unless `--llm` is explicitly requested.
- Added regression coverage for latest-Markdown selection when `young send` is run without an explicit date.

## [0.2.10] - 2026-06-19

### Fixed

- Hardened persisted LLM auth so saved credentials survive terminal restarts even when a stale environment variable is present.
- Switched `young chat` input handling to a prompt toolkit-backed editor to reduce backspace/cursor glitches on macOS terminals.

## [0.2.9] - 2026-06-19

### Changed
- `young chat` now auto-uses the existing `reach` bridge for explicit finance/news lookup requests, but only feeds compact evidence excerpts to the model instead of exposing raw search captures in the terminal.
- `young chat` input now uses `prompt_toolkit` with a fixed, non-editable `young ` prompt prefix for reliable backspace and cursor movement on macOS terminals.
- Help text now makes the command boundary clearer: `young daily --llm` is the strict stock-analysis M1-M6 Markdown replay, `young replay` is only a deprecated alias, and `young report` is PDF export only.

### Fixed
- Fixed chat search flows that previously surfaced raw `/reach` output or still nudged users to run `/reach` manually instead of returning a summarized answer directly.
- Hardened LLM replay prompts so `young daily --llm` stays on the stock-analysis six-module framework and does not drift into persona-style investment templates.
- Fixed LLM config persistence so `young config llm --api-key-env ...` also stores a local fallback key, which keeps `young chat` working across fresh terminal sessions without forcing users to re-export the secret every time.
- Fixed stale shell environment variables overriding the saved API key after terminal restarts; saved credentials now take precedence and accidental outer quotes or whitespace are normalized.

## [0.2.8] - 2026-06-19

### Added
- `young chat` now cross-checks Beijing time with both local clock and lightweight online HTTP Date sources, using whichever path is available as a safe fallback.

### Changed
- Chat time grounding now refreshes with a five-minute verification cache so relative phrases like “今天”“当前”“最新” stay anchored to current Beijing time without adding heavy network overhead.
- Chat now auto-invokes the existing `young reach` bridge only for explicit search/latest-news/company-info requests, then feeds the result back into the LLM as evidence instead of claiming it cannot search.

### Fixed
- Fixed chat answers that could hallucinate stale absolute dates when users asked for the current date or time.
- Fixed interactive input deletion issues by switching the chat prompt loop away from `Rich Prompt.ask()` to a simpler console input path with native line-edit support.

## [0.2.7] - 2026-06-19

### Added
- Added an optional `young reach ...` / `/reach ...` bridge for local Agent-Reach setups, keeping external web/company research available without adding new runtime dependencies to the main package.

### Changed
- `young daily --llm` now prints the full report body in the terminal even when it reuses an existing Markdown artifact.
- Chat persona prompts now introduce themselves directly as the selected style persona, instead of falling back to `young-stock-cli 助手` or explaining that they are merely “按某种风格对话”.
- When evidence is insufficient for single-stock deep analysis, chat now prefers `/stock <symbol>`, `/analyze <symbol>`, or `/reach <query>` guidance instead of defaulting to a hard refusal.

### Changed
- `young chat` startup banner now explicitly teaches `/style set <name>` as the way to sync dialogue style, self-reference tone, and analysis framework.
- Style prompts now bind all three together: tone, first-person self-reference, and the selected investment framework are sent to the LLM in one contract.
- `young daily --llm` now stops at terminal output plus Markdown artifact generation, while `young report` remains the single PDF export path.
- `young init` now puts config and investment-memory setup ahead of optional reporting commands.

### Fixed
- Fixed style drift where old persona memory could pull the assistant back toward a different voice after `/style set <name>`.
- Fixed persistent chat config migration so `chat.style` and `chat.analysis_framework` converge to one synchronized value across restarts.

## [0.2.5] - 2026-06-19

### Added
- Added an authoritative chat slash-command whitelist and persistent `balanced`, `buffett`, `munger`, `graham`, and `dalio` analysis styles.
- Added A-share session detection for closed, pre-market, morning, midday, intraday, and after-hours report routing.
- Added safe clickable HTTP(S) news links to Markdown and PDF reports.

### Changed
- `young daily --llm` now generates or reuses matching Markdown and PDF artifacts; `--refresh` forces a rebuild.
- `young replay`, `/replay`, and `/daily-llm` remain compatibility aliases but now direct users to `young daily --llm`.
- `young report` remains a Markdown-to-PDF exporter and defaults to the latest available trading-date report.
- Public reports now use one concise disclosure under the title and natural missing-data language instead of mechanical placeholder paragraphs.
- Updated README guidance to match the current command surface: `young daily` is the deterministic watchlist report, `young daily --llm` is the deep after-hours replay with shared identity and `--refresh` rebuilds, `young replay`/`/daily-llm`/`/replay` are deprecated aliases, and chat documents its curated authoritative whitelist plus the `/style` framework.
- Updated install and export guidance to emphasize `young init` as an initialization/verification step, `young report` as the Markdown-to-PDF export path, and the PDF/report hygiene rules that keep links clickable and remove mechanical placeholder wording.

### Fixed
- Prevented chat from recommending nonexistent commands or invoking blocked configuration, delivery, update, uninstall, and other mutating command paths.
- Made PDF export select an explicit report identity instead of relying on modification-time ordering when multiple same-day reports exist.
- Kept missing LLM configuration recoverable through deterministic daily output while preserving authentication and network failures as errors.

## [0.2.4] - 2026-06-19

### Added
- Added persistent long-term chat memory with dedicated `young memory show|clear|reset` management commands.
- Added `young init` to initialize local state and check report/LLM readiness in one step.

### Fixed
- Fixed `young report` to prefer identity-based Markdown/PDF artifacts over legacy `replay.*` files and to sanitize legacy reports before export.
- Fixed report/session routing so `young report` defaults to the current calendar date and historical report exports stay tagged as `盘后`.
- Fixed exported Markdown/HTML/PDF to remove the fixed “资深A股交易员”前言 and `Kami-compatible editorial layout` residue.
- Fixed `young send` to deliver the identity-matched PDF instead of looking only for `report.pdf`.
- Fixed installation guidance so the default package path includes PDF support and the readiness/error messages point to the same install flow.

## [0.2.3] - 2026-06-18

### Added
- Added a mandatory research-style boundary that converts internal evidence and stock-analysis methodology into publication-safe investment language before LLM synthesis.
- Added a second report review pass that removes Markdown-wrapped internal fields, technical terms, local locations, and implementation filenames before persistence.
- Added shared board and fund-flow routing for `young a` and LLM evidence, including optional Camofox and Playwright page retrieval after public data endpoints.
- Added date/session/topic report identities such as `20260618-盘后-A股深度复盘.md`.

### Changed
- Reports generated in the same trading date, session, and topic now overwrite the prior artifact; reports from other sessions remain available.
- Markdown, HTML, PDF, Evidence, and metadata now share the date/session/topic identity.
- Legacy generic report files no longer take precedence once a session-aware report exists.
- LLM auth failures now surface the provider response message and a concrete Ark model-discovery hint without exposing secrets.

## [0.2.2] - 2026-06-18

### Fixed
- Made stock-analysis updates strictly version-gated: remote content is installed only when its semantic version is greater than the verified local version.
- Downloaded the reporting specification, output discipline, data-source strategy, M1-M6 methodology, and templates as one text-only bundle.
- Added SHA-256 manifests and read-time validation for the cached methodology bundle; failures retain the last verified local or bundled specification.
- Kept the security boundary explicit: no remote Python, JavaScript, shell code, package, or repository checkout is executed by report generation.

## [0.2.1] - 2026-06-18

### Added
- Added `young config models` for provider-neutral model discovery across Ark and other OpenAI-compatible services, Kimi/Moonshot, DeepSeek, Qwen, Anthropic, and Ollama endpoints.
- Added report-time stock-analysis specification checks with safe text-only caching; remote code is never executed.

### Fixed
- Translated internal Evidence Pack fields into research language before LLM synthesis and sanitized engineering terminology from final reports.
- Allowed verified fund-flow data to keep the sector/fund-flow module available when board rankings are temporarily absent.
- Unified `young a` and LLM evidence board routing so both try the lightweight source and then the configured Camofox browser path.
- Converted Camofox board snapshots into the same structured row format used by normal board rankings.
- Expanded uv tool installation and PDF dependency guidance in README and command errors.

## [0.2.0] - 2026-06-18

### Added
- Added versioned LLM and delivery-channel configuration in `~/.young_stock/config.json`, including masked display and environment-based API key lookup.
- Added OpenAI-compatible providers (OpenAI, DeepSeek, Qwen, Ollama) plus Anthropic message support with timeouts, retries, and safe errors.
- Added `young chat`, a Rich interactive REPL whose curated authoritative whitelist routes selected safe/read-only commands through Click.
- Added evidence-driven `young replay`, `young daily --llm`, and `young analyze <symbol>` workflows based on the stock-analysis M1-M6 methodology and quality-score degradation.
- Added persistent report/evidence artifacts under `~/.young_stock/reports/YYYYMMDD/`.
- Added `young report` with automatic deterministic-report fallback and optional WeasyPrint PDF export using a Kami-compatible Equity Report layout.
- Added modular `young send` delivery with Feishu webhook preview mode and Feishu App Markdown/PDF attachment mode.

### Changed
- Extended `young diagnose --json` with non-secret LLM, PDF, report, and configured-channel readiness.
- Version advanced to 0.2.0 for the new optional AI/reporting surface; all existing commands remain available without LLM or PDF dependencies.

## [0.1.22] - 2026-06-15

### Changed
- README and package long description now match the current stable-source strategy: Sina/Tencent are the default quote path, while Eastmoney-style interfaces stay behind explicit supplemental commands or CLI-managed fallback layers.
- Default multi-source news heat aggregation now prioritizes stable no-login sources (Futu + Sina) instead of treating Eastmoney fast news as a standard ranking input.
- Market headers and user-facing copy now describe the current source policy more accurately, reducing confusion between default main sources and on-demand supplemental sources.

## [0.1.21] - 2026-06-15

### Added
- `young a` now includes Tonghuashun northbound intraday cumulative flow, so A-share dashboards pick up the stable northbound source directly.
- `young a` now fetches Eastmoney industry/concept board rankings through a lightweight clist request before falling back to the optional browser board page.

### Changed
- Completed the command-wide upstream review: Yahoo-backed K-line/options/holders/news, iwencai, mootdx, and high-frequency Eastmoney push2 paths remain outside the default CLI path because they add login/API-key/dependency or stability risk.

## [0.1.20] - 2026-06-15

### Added
- Added `young flow --stock <symbol>` for on-demand A-share/HK/US single-stock daily fund flow from Eastmoney `push2his`, including main/small/mid/big/super-big order net flow.
- Added `young flow --northbound` for Tonghuashun northbound intraday cumulative flow, avoiding the previously unreliable Eastmoney northbound path.
- Added `young block-trades <symbol>` for recent A-share block-trade records from Eastmoney datacenter, including deal price, discount/premium, amount, buyer, and seller seats.

### Changed
- Yahoo-backed upstream data remains excluded from the primary CLI path; Eastmoney `push2his` fund flow is used only for explicit per-stock requests and is labeled as a supplemental source.

## [0.1.19] - 2026-06-15

### Added
- Added Tencent Finance stock quotes as a verified enrichment source for A-share, Hong Kong, and US single-stock snapshots, market focus-stock sections, and fund holding quotes.
- Single-stock output now shows turnover, turnover rate when available, market cap, PE/PB, and 52-week range when a validated no-login source provides those fields.

### Changed
- Sina Finance remains the primary quote path for HK/US focus stocks, while Tencent now supplements missing valuation/liquidity fields before Eastmoney `stock/get`/`clist` fallback is used.

## [0.1.18] - 2026-06-14

### Fixed
- Cache reads no longer create cache directories, avoiding permission-related failures when the cache path is not writable.
- A-share index loading now ignores invalid cached/API shapes instead of passing non-list data to the renderer.

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
