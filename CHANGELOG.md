# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-31

### Added
- Initial public release.
- `young a` / `hk` / `us` / `global` subcommands.
- A-share post-market replay: indices, 涨停/跌停/炸板 pool, fund flow,
  industry & concept sector rankings (via browser fallback).
- HK & US replays via Eastmoney `clist` batch endpoint (no-login, no rate limit).
- Three-tier fetch strategy: cache → stable JSON API → browser fallback
  (camofox / Playwright / Hermes built-in browser).
- Data-quality scoring + diagnostic reporting for every run.
- Cross-market sentiment summary for `young global`.
