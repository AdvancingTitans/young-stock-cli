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

```bash
python3 -m pip install young-stock-cli
```

Requires Python 3.9+.

If `pip3 install young-stock-cli` reports that every release requires a different Python version, your
`pip3` is attached to an older Python. Check with `python3 --version`, then install or upgrade with a
Python 3.9+ interpreter:

```bash
python3 -m pip install --upgrade young-stock-cli
```

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
young daily --format summary      # concise personalized daily report
young daily --format key-points   # short report with trend/risk points
young daily --format full         # full personalized daily report
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
young a -d 20260530     # historical date (YYYYMMDD)
young a --refresh       # bypass cache, force re-fetch
young update            # upgrade young-stock-cli in the current Python env
young uninstall         # uninstall from the current Python env
young --help
```

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

- **Multiple public quote sources** — Tencent Finance, Sina Finance, and Eastmoney are tried in sequence so temporary source failures can be filled by another no-login endpoint.
- **Single-stock lookup** — `young stock 600519`, `young stock 0700.HK`, or `young stock AAPL` prints a compact quote snapshot with source, trade date, price, change, volume, turnover when available, and optional news.
- **Fund holding lookup** — `young fund 161725` prints the fund's same-day estimated change, latest NAV date, top holdings, holding-stock quotes, rough contribution estimate, and same-day holding-stock news. Official fund NAVs usually update at night, so intraday/close values are clearly labeled as estimates.
- **Personal daily report** — `young daily` reads your local investment memory from `~/.young_stock/profile.json`, then prints saved stock/ETF trends, fund estimates, only the markets relevant to your stocks and fund top holdings, and portfolio-style suggestions grounded in your funds, stocks, holding dates, quantities, and available news. First use requires a verified symbol plus `--buy-date` and `--quantity`, for example `young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100` or `young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000`.
- **Short report modes** — `young daily --format summary` keeps terminal output compact; `--format key-points` adds a few trend/risk bullets; `--only`, `--order`, and `--quick` trim slower or irrelevant sections.
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
- **News heat ranking** — HK/US focus stocks can be ranked by filtered news heat from multiple no-login sources: Futu, Sina Finance, and Eastmoney fast news. Xueqiu/THS are intentionally not hardwired unless a stable no-login interface is available.
- **Same-day news discipline** — news sections only show items published on the requested trading date, up to five items, with a clear empty-state message when nothing valid is available.
- **Readable news links** — linked news items are checked for obvious empty/404/no-content pages and replaced by other same-day news when possible.
- **Sector boards via browser fallback** — when Eastmoney's board API rate-limits, falls back to rendering the public web page (optional, requires a local browser engine).
- **Local updater/uninstaller** — `young update` runs `python -m pip install --upgrade young-stock-cli`; `young uninstall` runs `python -m pip uninstall -y young-stock-cli` with the same interpreter that launched the CLI.

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
young global       # 全球指数一屏
young a -d 20260530 --refresh    # 指定日期 + 强制刷新
young update       # 在当前 Python 环境中更新 CLI
```

数据来源：同花顺概念资金流页面（仅在同时拿到净流入/净流出榜时采用）、腾讯财经、新浪财经、东方财富公开行情与快讯接口（`data.10jqka.com.cn` / `qt.gtimg.cn` / `hq.sinajs.cn` / `push2.eastmoney.com` / `push2ex.eastmoney.com` / `np-listapi.eastmoney.com`），多源自动切换。本地缓存 7 天，目录 `~/.young_stock/cache/`，可用 `young cache-clear` 清理。命令会标注当前阶段：上午盘、午间、下午盘或盘后；若展示的是非请求日的最新可用数据，会标注为该交易日盘后数据。普通输出不展示完整度和数据源诊断，排查问题时可设置 `YOUNG_STOCK_DEBUG=1` 查看详细切换记录。

适用人群：每天盘后想用一条命令看完五张图的开发者 / 量化研究者 / 自动化爱好者。欢迎 issue / PR。
