# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
