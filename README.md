# young-stock-cli

[![PyPI](https://img.shields.io/pypi/v/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![Python](https://img.shields.io/pypi/pyversions/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![License](https://img.shields.io/pypi/l/young-stock-cli.svg)](https://github.com/AdvancingTitans/young-stock-cli/blob/main/LICENSE)
[![CI](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml)
[![Downloads](https://static.pepy.tech/badge/young-stock-cli/month)](https://pepy.tech/project/young-stock-cli)

> An A-share (China stock market) after-hours CLI that **just works** — no login, no API keys, no scraping tricks.
> Also covers HK & US indices and a global snapshot.

A single command (`young a`) prints a complete after-hours dashboard: major indices, limit-up (涨停) and limit-down pools, latest verified A-share fund flow with the source trading date, current session stage, and top sector boards. Everything pulls from public no-login endpoints, with a 7-day local cache so repeated calls during the same session don't hammer the server.

Born out of a real workflow: every trading day after close I wanted the same five numbers in one place without opening a browser or paying for a data terminal. So I packaged it.

---

## Install

Recommended for CLI isolation:

```bash
uv tool install young-stock-cli && young init
```

Or install into the active Python environment:

```bash
python3 -m pip install --upgrade young-stock-cli && young init
```

If you need the plain install form for an existing environment, `python3 -m pip install young-stock-cli` still works.
If you upgraded from an older uv-managed environment, `uv tool install --force 'young-stock-cli'` is the quick
refresh path.

Requires Python 3.9+.

If `pip3 install young-stock-cli` reports that every release requires a different Python version, your
`pip3` is attached to an older Python. Check with `python3 --version`, then install or upgrade with a
Python 3.9+ interpreter:

```bash
python3 -m pip install --upgrade young-stock-cli
```

If you installed `young` with `uv tool`, upgrade that tool-managed environment instead of `pip`:

```bash
uv tool install --upgrade young-stock-cli
```

`young init` creates the local home/profile files, verifies whether PDF rendering is available in the current
environment, and prints the recommended next steps. It only initializes and verifies; it does not auto-edit your
shell environment or install extra packages. You only need to install the tool once per environment; you do not need
to reinstall it before every report.

If `python3 -m pip install --upgrade young-stock-cli` succeeds but `young --version` still shows an older release,
you are probably running a different executable entrypoint than the interpreter you just upgraded. A quick check:

```bash
which -a young
young --version
uv tool list
python3 -m pip show young-stock-cli
```

If `which young` points to `~/.local/bin/young`, that command is usually coming from `uv tool`, not from the
`python3 -m pip` environment.

## Usage

```bash
young a                 # A-share after-hours dashboard (the main thing)
young a --no-news       # A-share dashboard without news links
young hk                # Hong Kong indices snapshot
young us                # US indices snapshot
young global            # A + HK + US in one view
young stock 600519      # one stock snapshot (A-share / HK / US)
young fund 161725       # fund estimate + top holdings quote/news
young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100
young profile add-stock NVDA --buy-date 2026-01-15 --quantity 10
young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000
young profile add-fund 021528 --buy-date 2026-01-10 --quantity 1000
young profile list
young profile clear-stocks  # clear all saved stocks/ETFs only
young profile clear-funds   # clear all saved funds only
young daily --format summary      # deterministic watchlist daily report; no LLM needed
young daily --format key-points   # short deterministic report with trend/risk points; no LLM needed
young daily --format full         # full deterministic watchlist daily report; no LLM needed
young daily --llm                 # the only deep after-hours / latest-trading-day replay entry; saves Markdown
young daily --llm --refresh       # rebuild the same identity from scratch
young init                       # initialize local state and verify report/PDF readiness
young analyze 600519             # deep single-stock analysis
young reach 贵州茅台 盈利 新闻    # optional Agent-Reach bridge for external web/company research
young chat                       # Rich chat mode with slash commands
young report                     # export the latest Markdown report to PDF
young send                       # send latest Markdown + summary; attach same-name PDF only if it exists
young daily --only 基金,A股 --quick
young news 3690.HK      # multi-source news only
young diagnose          # network/source diagnostic
young diagnose --json   # machine-readable support diagnostic
young note add "today I reduced chasing"
young alert create 600519 "涨跌幅>5%"
young stock AAPL --no-news
young fund 161725 --no-news
young us --no-news      # market data only, skip news links
young indices           # A-share indices only
young zt-pool           # limit-up (涨停) / limit-down / 炸板 pool
young flow              # latest verified A-share fund flow
young flow --stock 0700.HK --limit 5  # one-stock daily fund flow (A/HK/US)
young flow --northbound # northbound intraday flow from Tonghuashun
young block-trades 600519 --limit 5   # A-share block trade records
young a -d 20260530     # historical date (YYYYMMDD)
young a --refresh       # bypass cache, force re-fetch
young update            # upgrade young-stock-cli in the current Python env
young uninstall         # uninstall from the current Python env
young --help
```

### LLM configuration and chat

LLM features are optional. Existing market commands do not require a model or API key. Configuration is stored in
`~/.young_stock/config.json` (or `$YOUNG_STOCK_HOME/config.json`).

```bash
# Prefer an environment variable so the key is not stored in config.json
export DEEPSEEK_API_KEY="..."
young config llm \
  --provider deepseek \
  --model deepseek-chat \
  --api-key-env DEEPSEEK_API_KEY

# Other supported providers
young config llm --provider openai --model gpt-4.1 --api-key-env OPENAI_API_KEY
young config llm --provider qwen --model qwen-plus --api-key-env DASHSCOPE_API_KEY
young config llm --provider anthropic --model claude-sonnet-4-20250514 --api-key-env ANTHROPIC_API_KEY
young config llm --provider ollama --model qwen2.5:14b --api-base http://localhost:11434/v1

young config show       # secrets are masked
young config path
```

Model IDs are provider-specific and change over time. Do not rely on a console display name such as
`Kimi-K2.6` or `ark-code-latest`; query the endpoint and copy an exact returned ID:

```bash
# Use saved provider/api_base/api_key_env settings
young config models

# Ark / Volcano Engine (OpenAI-compatible)
export ARK_API_KEY="..."
young config models \
  --provider ark \
  --api-key-env ARK_API_KEY

# Kimi / Moonshot
export MOONSHOT_API_KEY="..."
young config models \
  --provider kimi \
  --api-key-env MOONSHOT_API_KEY

# DeepSeek and Qwen can use their built-in API bases
young config models --provider deepseek --api-key-env DEEPSEEK_API_KEY
young config models --provider qwen --api-key-env DASHSCOPE_API_KEY

# Local Ollama
young config models --provider ollama --api-base http://localhost:11434/v1
```

For endpoint-level troubleshooting, the equivalent OpenAI-compatible request is:

```bash
curl -sS "$API_BASE/models" \
  -H "Authorization: Bearer $MODEL_API_KEY" |
python3 -c 'import json,sys; print("\n".join(x["id"] for x in json.load(sys.stdin).get("data", [])))'

# Ark exact example
curl -sS https://ark.cn-beijing.volces.com/api/v3/models \
  -H "Authorization: Bearer $ARK_API_KEY" |
python3 -c 'import json,sys; print("\n".join(x["id"] for x in json.load(sys.stdin).get("data", [])))'

# Kimi / Moonshot exact example
curl -sS https://api.moonshot.cn/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" |
python3 -c 'import json,sys; print("\n".join(x["id"] for x in json.load(sys.stdin).get("data", [])))'
```

For Ark, set `API_BASE=https://ark.cn-beijing.volces.com/api/v3`; for Kimi/Moonshot, set
`API_BASE=https://api.moonshot.cn/v1`. After selecting an ID, pass the same API base to `young config llm`.
Some coding-plan names and web-console aliases are not Chat Completions model IDs.

```bash
# Configure the exact ID returned above
young config llm --provider ark --model "<ark-model-or-endpoint-id>" --api-key-env ARK_API_KEY
young config llm --provider kimi --model "<moonshot-model-id>" --api-key-env MOONSHOT_API_KEY
```

Start the interactive mode with `young chat`. A curated authoritative whitelist routes selected safe/read-only
commands through Click:

```text
/a
/stock 600519
/fund 161725
/reach 贵州茅台 盈利 新闻
/daily --format summary
/daily --llm
/profile list
/style
/style list
/style set balanced
/style show
/style clear
/report
```

The chat keeps the five most recent user/assistant turns. If no LLM is configured, enhanced commands fail with a
configuration hint while `/a`, `/stock`, `/daily`, and every other deterministic command continue working. `/daily`
without `--llm` stays deterministic and does not require LLM. Chat is authoritative and only exposes a white-listed
command surface: do not expect `/market` or `/trend`, and `/send`, `/config`, `/update`, and `/uninstall` are
intentionally blocked from chat.

The style commands persist under chat config and synchronously set dialogue tone, self-reference style, and analysis
framework. Supported styles are `balanced`, `buffett`, `munger`, `graham`, and `dalio`.

`young reach ...` and `/reach ...` are optional bridges to a local Agent-Reach setup. They do not add new runtime
dependencies to `young-stock-cli`: if `mcporter`, `curl`, or `agent-reach` are not installed, young prints an install
hint instead of silently failing. Use them when you need external company news, earnings context, or webpage reading
without making the main CLI package heavy.

### Evidence-driven deep replay

`young daily --llm` builds an Evidence Pack entirely from the structured values returned by `young_stock._core`. It is
the only LLM replay entry. The model is used for synthesis, not data collection.

The report follows the six-module method from
[`AdvancingTitans/stock-analysis`](https://github.com/AdvancingTitans/stock-analysis):

1. M1 index overview
2. M2 sector and fund flow
3. M3 upside/limit-up effect
4. M4 downside and blow-up risk
5. M5 market/portfolio style
6. M6 resilient directions

Before each LLM replay, young checks the remote `stock-analysis` version. It installs a text-only update only when
the remote semantic version is greater than the locally cached/bundled version. `SKILL.md`, output discipline,
data-source strategy, M1-M6 methodology files, and report templates are downloaded together, SHA-256 recorded in
`~/.young_stock/methodologies/stock-analysis/manifest.json`, and verified when read. Remote code is never executed,
and the browser or external repo is not a chat runtime dependency. If checking, downloading, or validation fails,
young keeps the last verified local specification or bundled guidance.

Each module has an evidence score. Missing fields remain missing rather than being rendered as zero. Low-quality
evidence automatically produces a shorter report limited to verified indices, holdings, risks, and next-session
checks. Markdown, metadata, and `evidence.json` are retained under:

```text
~/.young_stock/reports/YYYYMMDD/
```

Before the model sees any data, young converts internal evidence into research-only Chinese terminology. The same
conversion is applied to the downloaded stock-analysis methodology, so implementation guidance never enters the
report-writing context. The returned Markdown is reviewed again before it can be saved or exported. Formal reports
use only these source phrases:

- normal data: `据公开市场数据`, `据交易所及财经终端披露`
- missing data: `该指标当日未披露`, `历史数据不可得`
- historical lookback: `按惯例回溯至该日`, `历史口径回溯`

The mechanical placeholder `本模块证据暂缺` is cleaned from the final publication text and should not be treated as a
recommended output phrase.

Report artifacts include the date, market session, and topic:

```text
20260618-早盘-A股深度复盘.md
20260618-盘中-A股深度复盘.md
20260618-盘后-A股深度复盘.md
20260618-盘后-600519深度分析.md
```

Generating the same topic again in the same session replaces the previous artifact. A report from another session
is retained.

### Professional PDF reports

The standard install already includes PDF support. If you upgraded from an older environment, refresh the tool once:

```bash
uv tool install --upgrade young-stock-cli
```

If `young` was installed into the active Python environment instead:

```bash
python3 -m pip install --upgrade young-stock-cli
```

Then export the latest Markdown report to PDF:

```bash
young report
young report --date 20260618
```

If no Markdown report exists for the selected date, `young report` first reuses a saved diary entry when available,
otherwise it automatically generates the latest available deterministic daily report. It is a Markdown-to-PDF export
command, not a stdout time-slice report. Run `young init` first if you want a quick readiness check for PDF
rendering, config, and local storage paths.

The PDF header is intentionally short, news links stay clickable, and the final report keeps the publication text
clean rather than echoing mechanical placeholders.

The bundled Equity Report layout follows the
[`tw93/Kami`](https://github.com/tw93/Kami) editorial language: parchment `#f5f4ed`, ink blue `#1B365D`,
serif-led hierarchy, compact rhythm, and print-ready A4 output. To use a locally installed Kami-derived template,
set `YOUNG_STOCK_KAMI_TEMPLATE` to an HTML file containing `{{TITLE}}`, `{{DATE}}`, and `{{BODY}}`.

### Feishu delivery

Webhook mode sends a text preview. Feishu incoming webhooks cannot upload arbitrary PDF attachments:

```bash
young config channel add feishu work \
  --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/..."
```

App mode uploads and sends Markdown first, then adds the same-name PDF when it exists:

```bash
young config channel add feishu research-app \
  --app-id "$FEISHU_APP_ID" \
  --app-secret "$FEISHU_APP_SECRET" \
  --receive-id "$FEISHU_CHAT_ID"

young config channel list
young config channel remove feishu work
```

One-click workflow:

```bash
young daily --llm
young report
young send

# Or target one date/channel
young send --date 20260618 --channel research-app
```

Requests use timeouts and bounded retries. Channel errors are reported independently, and secrets are masked in
configuration and diagnostic output.

### Example output (`young indices`)

```
A股主要指数 — 2026-05-30 收盘
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┓
┃ 指数                        ┃     收盘  ┃ 涨跌幅 ┃ 成交额  ┃ 振幅     ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━┩
│ 上证指数                    │  3,347.49 │ +0.62% │ 4,821亿 │ 1.18%   │
│ 深证成指                    │ 10,402.91 │ +0.95% │ 6,015亿 │ 1.42%   │
│ 创业板指                    │  2,135.66 │ +1.21% │ 2,310亿 │ 1.68%   │
│ 科创50                      │  1,028.74 │ +0.81% │ 412亿   │ 1.05%   │
└─────────────────────────────┴───────────┴────────┴─────────┴──────────┘
```

---

## Why this exists

Most A-share data libraries either (a) require paid accounts, (b) break the moment a portal redesigns its DOM, or (c) ship hundreds of MB of dependencies for a one-off after-hours glance. This is a 1-file core, three runtime deps (`requests`, `click`, `rich`), opinionated output, and a single command that prints what a trader actually wants at 15:01.

It is also a foundation for analysis pipelines: every subcommand maps to a Python function in `young_stock._core`, so you can `from young_stock._core import get_zt_pool, get_fund_flow` and feed the dicts into your own notebook or LLM prompt.

The internals are being split into focused modules: `young_stock.calendar` handles holiday-aware trade dates, `young_stock.profile` handles local investment memory, `young_stock.reports` composes daily reports, and `young_stock.health` tracks lightweight public-source health. Compatibility wrappers remain in `_core` for existing users.

## What's in the box

- **Multiple public quote sources** — Sina Finance and Tencent Finance are the default stable quote path; market-specific public interfaces stay behind the CLI fallback layer when no better source is available.
- **Single-stock lookup** — `young stock 600519`, `young stock 0700.HK`, or `young stock AAPL` prints a compact quote snapshot with source, trade date, price, change, volume, turnover, market cap, PE/PB, 52-week range when available, and optional news.
- **Fund holding lookup** — `young fund 161725` prints the fund's same-day estimated change, latest NAV date, top holdings, holding-stock quotes, rough contribution estimate, and same-day holding-stock news. Official fund NAVs usually update at night, so intraday/close values are clearly labeled as estimates.
- **Personal daily report** — `young daily` is the deterministic watchlist report from your local investment memory in `~/.young_stock/profile.json`; it does not require LLM, and it prints saved stock/ETF trends, fund estimates, only the markets relevant to your symbols and fund top holdings, and portfolio-style suggestions grounded in your funds, stocks, holding dates, quantities, and available news. First use requires a verified symbol plus `--buy-date` and `--quantity`, for example `young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100` or `young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000`.
- **LLM replay** — `young daily --llm` performs the deep after-hours / latest-trading-day replay, writes the matching Markdown artifact under the same report identity, and prints it in the terminal; `young report` is the dedicated PDF export step, and `--refresh` rebuilds the Markdown identity.
- **Short report modes** — `young daily --format summary` keeps terminal output compact; `--format key-points` adds a few trend/risk bullets; `--only`, `--order`, and `--quick` trim slower or irrelevant sections.
- **Chat style control** — `/style list|set|show|clear` persists one synchronized style choice for tone, self-reference, and analysis framework. `balanced`, `buffett`, `munger`, `graham`, and `dalio` are style contracts, not identity claims.
- **Investment memory management** — list, remove, clear, and group saved stocks/funds with `young profile list`, `remove-stock`, `remove-fund`, `clear`, `clear-stocks`, `clear-funds`, and `profile group create/add`.
- **Local workflow helpers** — lightweight `portfolio`, `alert`, `note`, and `diary` commands store local records for portfolio experiments, reminder rules, investment notes, and saved daily-report text.
- **Diagnostics** — `young diagnose` summarizes recent source health and suggests cache/quick-mode fallbacks when public APIs are unstable; `young diagnose --json` prints read-only, machine-readable support info with Python/version/path/source-health details.
- **Single-stock news** — `young news 3690.HK` prints only the news/momentum view, with each item showing source and link status.
- **Smart caching** — `~/.young_stock/cache/`, 7-day TTL, auto-pruned. Pass `--refresh` to skip.
- **Trade-day awareness** — nearest-trade-day resolution including weekends and (best-effort) holidays.
- **Formal calendar layer** — A-share/HK/US holiday sets are separated into `young_stock.calendar`, so trading-day rules can evolve without touching data-source code.
- **Source health tracking** — common JSON fetches update `young_stock._core.SOURCE_HEALTH`, giving downstream agents a recent success-rate/latency signal for public sources.
- **Rich terminal tables** — readable on dark and light terminals.
- **Verified A-share fund flow** — `young flow` uses Tonghuashun concept-board fund flow only when both net-inflow and net-outflow rankings are available, then falls back to Eastmoney main-capital flow/page indicators, Sina Finance sector fund-flow, Sina/Tencent market-activity references, and finally the most recent locally cached good record. Non-equivalent fallbacks are clearly labeled instead of being presented as whole-market main-capital net inflow.
- **A-share dashboard flow and boards** — `young a` now also prints Tonghuashun northbound intraday flow and Eastmoney industry/concept board rankings; if the lightweight board API is unavailable, the optional browser fallback is still used.
- **One-stock fund flow** — `young flow --stock 600519`, `young flow --stock 0700.HK`, and `young flow --stock AAPL` show daily main/small/mid/big/super-big order net flow from Eastmoney `push2his`. This is an on-demand supplement, not a replacement for the primary quote path, because the source can occasionally be network/IP rate-limited.
- **Northbound flow** — `young flow --northbound` uses Tonghuashun `hsgtApi` minute cumulative northbound flow, avoiding the Eastmoney northbound path that stopped being reliable after 2024.
- **A-share block trades** — `young block-trades 600519` shows recent block-trade records from Eastmoney datacenter, including trade date, deal price, discount/premium, amount, buyer, and seller seats.
- **News heat ranking** — HK/US focus stocks can be ranked by filtered news heat from stable no-login sources: Futu and Sina Finance. Xueqiu/THS/Eastmoney news are intentionally not hardwired as default hotness inputs unless a stable public interface is verified.
- **Same-day news discipline** — news sections only show items published on the requested trading date, up to five items, with a clear empty-state message when nothing valid is available.
- **Readable news links** — linked news items are checked for obvious empty/404/no-content pages and replaced by other same-day news when possible.
- **Sector boards via browser fallback** — when Eastmoney's board API rate-limits, falls back to rendering the public web page (optional, requires a local browser engine).
- **Local updater/uninstaller** — `young update` runs `python -m pip install --upgrade young-stock-cli`; `young uninstall` runs `python -m pip uninstall -y young-stock-cli` with the same interpreter that launched the CLI. For fresh setups, prefer `uv tool install young-stock-cli && young init`, or `python3 -m pip install --upgrade young-stock-cli && young init` in an active interpreter.

## Library usage

```python
from young_stock._core import get_index, get_zt_pool, nearest_trade_date

date = nearest_trade_date()
print(get_index(date))
print(get_zt_pool(date))
```

## Development

```bash
git clone https://github.com/AdvancingTitans/young-stock-cli.git
cd young-stock-cli
python3 -m pip install -e ".[dev]"
pytest
ruff check .
```

## Roadmap

- [ ] Optional JSON output (`--json`) for piping into downstream tools.
- [ ] Built-in trading-calendar (公开节假日) for accurate non-trade-day skipping.
- [ ] Plugin hooks for additional data sources (THS, Sina).
- [ ] `young watch` — live ticker mode during trading hours.

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

---

## 中文说明

A 股盘后行情命令行工具。免登录、免 API key、免反爬技巧 — 一行命令把当日涨跌、涨停板、可核验的 A 股资金流向、板块榜全部打到终端。同时支持港股、美股指数和全球快照视图。

```bash
python3 -m pip install young-stock-cli
young a            # A 股盘后总览（主命令）
young a --no-news  # 只看 A 股行情与情绪，跳过新闻
young stock 600519 # 单只股票速览（A股 / 港股 / 美股）
young fund 161725  # 基金估算收益 + 持仓股行情/新闻
young news 3690.HK # 单只股票消息面，多源新闻与链接
young fund 161725 --no-news # 只看基金估算与持仓行情
young hk --no-news # 只看行情，跳过新闻链接
young zt-pool      # 涨停 / 跌停 / 炸板分析
young flow         # 最新可核验 A 股资金流向
young flow --stock 0700.HK --limit 5  # 单股日级资金流（A股 / 港股 / 美股）
young flow --northbound # 同花顺北向分钟累计流向
young block-trades 600519 --limit 5 # A股大宗交易
young global       # 全球指数一屏
young a -d 20260530 --refresh    # 指定日期 + 强制刷新
young update       # 在当前 Python 环境中更新 CLI
```

数据来源：同花顺概念资金流页面（仅在同时拿到净流入/净流出榜时采用）、同花顺北向 `hsgtApi`、腾讯财经、新浪财经，以及 A 股专项能力所需的公开接口（板块榜、涨跌停池、个股资金流、大宗交易、基金估值/持仓等）。单只股票和基金持仓股会用腾讯财经补充成交额、换手率、市值、PE/PB、52 周高低等字段；价格主口径优先使用当前验证更稳的新浪/腾讯链路，东财相关接口仅在缺口补洞或专项命令中按需调用，并在输出中标注来源。Yahoo 相关数据源未内置为主链路；mootdx/iwencai 等需要新增依赖或 API key 的能力暂不并入默认 CLI。本地缓存 7 天，目录 `~/.young_stock/cache/`，可用 `young cache-clear` 清理。命令会标注当前阶段：上午盘、午间、下午盘或盘后；若展示的是非请求日的最新可用数据，会标注为该交易日盘后数据。普通输出不展示完整度和数据源诊断，排查问题时可设置 `YOUNG_STOCK_DEBUG=1` 查看详细切换记录。

适用人群：每天盘后想用一条命令看完五张图的开发者 / 量化研究者 / 自动化爱好者。欢迎 issue / PR。
