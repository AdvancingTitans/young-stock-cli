# 推广文案 — young-stock-cli

发布时机建议：v0.1.0 在 PyPI 上线后再发，文案里的 `python3 -m pip install` 才有效。

---

## 一、小红书版（300 字内 + 配图 3-4 张）

**标题选项**（A/B 测试，挑一个发）：
1. 周末写了个 A 股盘后命令行，免登录，一行命令出全部数据
2. 受不了每天盘后开 5 个网页，自己撸了个 CLI
3. 终端党的 A 股盘后神器（开源）

**正文**：

每天 15:01 都要刷一遍上证、深成指、创业板、涨停板、北向资金…开网页太慢，付费终端没必要，干脆自己写了个命令行。

```
python3 -m pip install young-stock-cli
young a
```

一行命令把指数 + 涨停跌停 + 资金流向 + 板块榜全部打到终端 ✨

特点：
🟢 免登录、免 API key、免反爬技巧
🟢 数据来自东方财富公开接口，跟官网同源
🟢 7 天本地缓存，重复查不爆服务器
🟢 支持港股、美股、全球指数视图
🟢 MIT 开源，欢迎 star / issue / PR

GitHub: github.com/AdvancingTitans/young-stock-cli

适合人群：每天看盘的开发者、量化新手、自动化爱好者、爱折腾终端的人。

#A股 #开源项目 #命令行工具 #Python #量化交易 #程序员日常 #终端美学

**配图**：
- 图 1：`young a` 终端截图（最炸的那张，颜色丰富）
- 图 2：`young global` 全球指数表格
- 图 3：`young zt-pool` 涨停板分析
- 图 4：GitHub 仓库首页带 README 徽章

---

## 二、掘金版（技术深度版，备用）

**标题**：周末撸了个 A 股盘后 CLI：免登录 / 免 API key / pip 一键装

**正文骨架**：

### 起因
每天盘后想看的几个数据：四大指数、涨停板数 / 连板天梯、北向资金、板块热点。开 5 个网页太慢，akshare 装一次拖 200MB 依赖，tushare 要 token 还限流。一气之下自己撸。

### 设计目标
1. `python3 -m pip install` 装完就能用，无需任何账号配置
2. 三个运行时依赖：`requests` + `click` + `rich`
3. 数据源单一可控：东方财富公开行情接口
4. 输出对终端友好：rich Table，深浅色都好看
5. 默认带 7 天本地缓存，重复查询无压力

### 用法
（贴 README 的 Usage 段 + 截图）

### 数据源选型踩坑
（讲东财 push2.eastmoney.com 和 push2ex.eastmoney.com 两个端点：免登录、字段稳定、JSONP/JSON 都支持、连板天梯字段藏在 `pool[].zttj.days` 这种细节）

### 板块榜的反爬陷阱
（讲 `m:90+t:2` 板块榜 API 经常返空，最后改用 headless 浏览器抓页面表格的方案）

### 工程化
- ruff + pytest + GitHub Actions（3.10/3.11/3.12 matrix）
- PyPI Trusted Publisher，打 tag 自动发包
- MIT License，issue/PR 模板齐全

### 仓库
github.com/AdvancingTitans/young-stock-cli — 欢迎 star。

---

## 三、V2EX 版（短帖，分享创造节点，备用）

**标题**：[分享创造] young-stock-cli — A 股盘后命令行，免登录免 API key

**正文**：

```
python3 -m pip install young-stock-cli
young a            # A 股盘后总览
young zt-pool      # 涨停 / 跌停 / 炸板分析
young flow         # 北向资金 + 主力资金
young global       # A + HK + US 一屏
```

数据来自东方财富公开接口，无需任何账号配置。三个依赖：requests / click / rich。本地缓存 7 天。

写它的原因：每天盘后开 5 个网页太蠢，付费终端又用不上几个功能。

GitHub: https://github.com/AdvancingTitans/young-stock-cli
PyPI: https://pypi.org/project/young-stock-cli/

MIT，欢迎 issue / PR / star。
