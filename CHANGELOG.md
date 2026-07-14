# Changelog

## [0.3.16] - 2026-07-15

### Added

- Add independent evidence, provider, transport, cache, global-market, news-radar, and read-only MCP modules without introducing any dependency on another project.
- Add source provenance and schema metadata to structured evidence, including bounded enhanced-research source material.

### Changed

- Reject live-only board routes for historical requests before making a network call.
- Make unsupported numeric or date claims blocking after one LLM repair attempt.
- Gate CI and publishing on lint, tests, and coverage, then smoke-test the built wheel before release.

### Fixed

- Save the local investment profile atomically, keep a last-known-good backup, recover a corrupt primary file, and refuse destructive overwrites when no valid backup exists.

## [0.3.15] - 2026-06-29

### Fixed

- Clarify the optional PDF install path for `uv tool` users: local source installs now point to `uv tool install --force '.[pdf]'`, while PyPI installs point to `uv tool install --upgrade 'young-stock-cli[pdf]'`, preventing accidental fallback from a local `0.3.14+` checkout to the older PyPI package.

## [0.3.14] - 2026-06-29

### Changed

- Keep chat slash help/prompt/routing on one shared command descriptor registry, so `/send`, `/report`, `/style`, and read-only command guidance no longer drift independently.
- Make `young send` explicit: `--dry-run` previews the resolved Markdown/PDF bundle and channel, and `--yes` is now required for the real remote send path.
- Move WeasyPrint into the optional `pdf` extra; `young init`, README install docs, and PDF export errors now point to `young-stock-cli[pdf]`.

### Fixed

- Stop `young config show` and `young config models --list` from silently persisting API keys sourced from `--api-key-env`; they now hydrate env secrets in memory only.
- Centralize send artifact selection through a shared Markdown/PDF bundle resolver instead of rediscovering the same-name PDF inside the channel layer.

## [0.3.13] - 2026-06-28

### Changed

- Treat single `--lens <expert>` reports as single-expert research: no hidden debate, no M7 section, and no committee final-advice subsections; the final chapter now uses the expert framework for attitude, holding advice, and risk notes.

## [0.3.12] - 2026-06-28

### Fixed

- Normalize generated report Markdown spacing: list indentation now uses consistent two-space nesting, repeated inline spaces are collapsed, and spaces between numbers and percent signs are removed.

## [0.3.11] - 2026-06-28

### Changed

- Fully revert LLM model configuration to the 0.3.8 single-model surface: no provider registry command, no quick/deep model fields, no `backend-url` alias, no `YOUNG_LLM_*` overrides, and no `LLMClient(mode=...)` routing.
- Keep Ark configuration on the legacy-compatible `--api-base` option, including `https://ark.cn-beijing.volces.com/api/coding/v3`.

## [0.3.10] - 2026-06-28

### Changed

- Revert model configuration back to a single `--model` field and remove the user-facing quick/deep model options.
- Document the Volcengine Ark compatible endpoint command for `https://ark.cn-beijing.volces.com/api/coding/v3`.

## [0.3.9] - 2026-06-28

### Changed

- Bump the release version for the current incremental architecture upgrade.

## [0.3.8] - 2026-06-24

### Fixed

- Use Chinese expert display names in Chinese `--lens` report title and holding-advice headings, for example `巴菲特持仓建议与风险提示` instead of `Buffett持仓建议与风险提示`.

## [0.3.7] - 2026-06-24

### Fixed

- Add explicit expert naming rules for specific `--lens` reports, including expert-specific title text and the final holding-advice heading.
- Clarify `young config models --list` in README as the preferred way for Coding Plan and multi-model users to find chat-callable model IDs.
- Relax `stock --llm` mechanical checks so natural single-stock reports are not blocked only because they use rating/action wording instead of fixed attitude words.
- Keep `numbers_grounded` advisory for LLM reports after repair; unsupported numeric claims remain visible in metadata but no longer block otherwise complete reports.

## [0.3.6] - 2026-06-24

### Changed

- Replace the old quote-only `young stock` command with the former deterministic/deep single-stock analysis flow; `young analyze` is no longer registered.
- Add query date and current market-stage context to query command output.

### Fixed

- Remove the invalid research-bridge setup hint from empty enhanced-evidence output and diagnostics.
- Respect `--no-news` in rich single-stock extras by skipping social/event lookups while keeping quote, LHB, financial, and technical evidence paths.

## [0.3.5] - 2026-06-24

### Fixed

- Make `young config models --list` verify actual `chat/completions` availability before displaying model IDs, so catalog-only or inaccessible Ark models are hidden.

## [0.3.4] - 2026-06-24

### Fixed

- Filter non-chat and `status=Shutdown` Ark model catalog entries from `young config models --list`, and clarify model-unavailable errors when a raw catalog ID is not callable.

## [0.3.3] - 2026-06-24

### Fixed

- Relax LLM report mechanical checks for normal market-report wording, including common index names and localized full dates.
- Accept formal daily-report synonyms such as 综合判断、综合持仓建议 and 下一交易日跟踪 without weakening unsupported financial-number checks.
- Treat `numbers_grounded` as an advisory metadata check after repair instead of blocking otherwise valid LLM daily reports.

## [0.3.2] - 2026-06-24

### Changed

- Documented that `young config models` must include `--model` when saving configuration.
- Consolidated model-list verification guidance around configured API keys and the OpenAI-compatible `/models` curl check.

### Fixed

- Reject Kimi Coding Plan endpoints for non-coding research workflows with a clear local error.
- Normalize Kimi Coding Plan vanity endpoints and model IDs before validation.
- Make LLM report repair prompts require the supported attitude labels.
- Allow grounded full dates such as `2026-05-29` when evidence contains the matching atomic date.

## [0.3.1] - 2026-06-21

### Added

- Ordered fallback models for compatible LLM endpoints via repeatable `--fallback-model`.
- Automatic evidence-based stock classification in profiles.

### Changed

- `young analyze` now matches `young daily`: LLM and lens layers are strictly opt-in.
- Human-facing commands, including `young lhb`, render readable output instead of raw JSON.

### Fixed

- Ark/OpenAI-compatible 404 and model-list errors now provide safe, actionable diagnostics.
- LLM retries and fallback distinguish transient, quota, authentication, SSL, and configuration failures.
- Numeric grounding preserves signs, percentages, decimals, symbols, and atomic dates.

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
