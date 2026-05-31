# young-stock-cli

[![PyPI](https://img.shields.io/pypi/v/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![Python](https://img.shields.io/pypi/pyversions/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![Downloads](https://img.shields.io/pypi/dm/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![CI](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A no-login command-line tool for end-of-day market replays across the
> A-share (Shanghai/Shenzhen/Beijing), Hong Kong, and US equity markets.
> Built on Eastmoney's public JSON endpoints with a browser fallback for
> anti-bot pages — **no API key, no account, no rate limit on the primary
> endpoints**.

---

## Why this exists

Most "free" stock-data packages for the Chinese market either (a) wrap a
single anti-bot website that breaks every few months, (b) require an
account on a paid data vendor, or (c) ship a heavy SDK for what is
really a 20-line HTTP call. `young-stock-cli` is the opposite: **one
binary, zero runtime dependencies, four commands**, and a documented
three-tier fallback when an endpoint goes down (cache → stable JSON API
→ headless browser).

If you write quant tooling for the A-share market, you have probably
written this script yourself. This is the maintained version.

## Install

```bash
pip install young-stock-cli
```

Python 3.8+ is supported. Zero runtime dependencies — only the standard
library.

## Quick start

```bash
young a              # A-share post-market replay (latest trading day)
young hk             # Hong Kong replay
young us             # US replay
young global         # Global indices snapshot (US + HK + A-share)
young a 20260526     # Specific trading day
young --help
```

### Sample output

```
$ young global

# 全球市场概览
数据来源: 东方财富免登录 API | 采集时间: 10:44:17

## 美股 大盘指数
指数              当前价      涨跌幅       成交量    数据质量
标普 500          75.80     +0.00%       54.74亿     100%
纳斯达克          269.73    +0.00%      109.70亿     100%

## 港股 大盘指数
恒生指数          251.82    +0.01%      297.25亿     100%

## A股指数表现
上证指数         4068.57   -0.73%    15320.67亿
深证成指        15575.13   -1.81%    17869.65亿
创业板指         4037.95   -2.11%     8556.62亿
科创50          1751.32   -5.04%     1821.40亿

📊 数据质量与诊断报告  平均完整度: 100%
```

## What it covers

| Market | Data |
|--------|------|
| **A-share** | Index quotes, 涨停/跌停/炸板 pools, board sentiment, fund flow, industry & concept sector rankings |
| **Hong Kong** | Index quotes (HSI/HSCE/HSTECH), individual stocks via `clist` batch endpoint |
| **US** | S&P 500, Nasdaq, individual ADRs, sector rotation |
| **Global** | One-shot cross-market summary with sentiment scoring |

## How it works

Three-tier fetch strategy, in order:

1. **Local cache** — 5 min TTL for live data, longer for end-of-day.
2. **Eastmoney stable JSON APIs** — `push2.eastmoney.com` for indices,
   `push2ex.eastmoney.com` for 涨停/跌停 pools, `clist` for batch quotes.
   No login, no rate-limit on these endpoints.
3. **Browser fallback** — sector rankings (`m:90 t:2` / `m:90 t:3`) are
   chronically rate-limited via JSON; we fall back to scraping the
   rendered page via [camofox-browser](https://github.com/daijro/camoufox),
   Playwright, or whichever browser engine is available.

Every record carries a **data-quality score** (0–100%) so downstream
consumers can decide whether to act on the data or wait.

## Library usage

The CLI is a thin wrapper. The functions in `young_stock_cli._core` are
importable:

```python
from young_stock_cli._core import (
    get_index,
    get_zt_pool,
    get_fund_flow,
    nearest_trade_date,
)

date = nearest_trade_date()
print(get_index(date))
print(get_zt_pool(date))
```

This API is stable from v0.1.0 onward and follows semver.

## Roadmap

- [ ] CSV / JSON / Parquet export flags
- [ ] WebSocket live ticks (intra-day)
- [ ] Tushare / Sina fallback when Eastmoney is down
- [ ] Simple TUI dashboard mode
- [ ] PyPI extras for Pandas DataFrame output

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## Contributing

Contributions are very welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Bug reports should include the trading day you queried, since
Eastmoney's payload format changes over time.

## License

MIT. See [LICENSE](LICENSE).

---

# young-stock-cli（中文）

A 股、港股、美股盘后行情命令行工具。基于东财公开接口，**免登录、免 API
Key、主接口不限流**，附带浏览器降级方案应对反爬页面。

## 安装

```bash
pip install young-stock-cli
```

支持 Python 3.8+，**零运行时依赖**。

## 快速上手

```bash
young a              # A 股盘后复盘（最近交易日）
young hk             # 港股盘后
young us             # 美股盘后
young global         # 全球指数概览
young a 20260526     # 指定交易日
```

## 覆盖范围

- **A 股**：上证/深证/创业板/科创/北证指数，涨停池/跌停池/炸板池，板块情绪，
  资金流向，行业板块榜、概念板块榜（浏览器抓取）
- **港股**：恒生 / 国企 / 科技指数，个股批量行情
- **美股**：标普、纳指、个股 ADR、板块轮动
- **全球**：跨市场综合情绪概览

## 三层获取策略

`本地缓存 → 东财稳定 JSON 接口 → 浏览器降级（camofox / Playwright）`。
每条记录附带 0–100% 的数据质量分，告诉调用方"这条数据能不能用"。

## 反馈与贡献

欢迎提 Issue 与 PR，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 协议

MIT。
