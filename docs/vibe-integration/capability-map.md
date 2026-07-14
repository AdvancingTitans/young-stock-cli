# Capability Map

核实日期：2026-07-08。
原则：本表以当前代码为准，不按 README 单独推断。Vibe-Research 参考仓库只读检查，临时克隆在当前仓库之外，未复制进 young。

## 能力类型

- 文档声明：Vibe README 或随仓 Skill 文档声明支持，但未必进入后端运行时。
- 后端 runtime：Vibe `backend/app.py`、`backend/*.py` 实际可被 FastAPI、Chat 或 MCP 调用。
- Skill-only：仅存在于 `a-stock-data/SKILL.md` 或 `global-stock-data/SKILL.md` 的可复制代码/说明，没有直接接入 Vibe 后端 runtime。

## 映射表

| 能力 | Vibe 当前实现位置 | young 当前实现位置 | young 当前是否已有骨架 | 建议 | 风险 | 目标阶段 |
|---|---|---|---|---|---|---|
| Provider Registry / 数据源注册 | 文档声明在 `backend/README.md`；后端 runtime 是分散函数与 FastAPI 路由；没有统一 registry | `src/young_stock/sources/contracts.py`、`registry.py`、`resolver.py`、`runtime.py` | 已有 | 适配：保留 young registry，把 Vibe 端点包成 adapter | 候选源和真实 adapter 不一致会误导 resolver | Provider Registry 与 API 供应商扩展 |
| SourceResult / Resolver / 健康检查 | Vibe 无等价通用抽象；局部缓存与异常处理在 `app.py`、`market.py`、`astock.py` | `SourceResult`、`SourceResolver`、`SourceHealthBook` | 已有 | 复用 young，不迁移 Vibe 结构 | 将 Vibe 直接函数接入时要补 `source/as_of/error/attempts` | Provider Registry 与 API 供应商扩展 |
| A 股实时行情 | 后端 runtime：`backend/astock.py` 的腾讯行情；FastAPI `/api/quote`、`/api/indices` | `_core.py` 的新浪、腾讯、东财 stock/get；`sources/adapters.py` 包装 quote | 已有 | 适配少量缺口，不替换主链路 | 腾讯字段为 0 的缺失语义需区别处理 | A 股扩展数据 |
| A 股指数 | 后端 runtime：`backend/astock.py` `index_quote` | `_core.py` `get_index`，东财失败后新浪、腾讯 | 已有 | 放弃迁移主实现，保留 young 多源链路 | 无 | A 股扩展数据 |
| 涨停、跌停、炸板池 | 后端 runtime：`backend/astock.py` `em_zt_topic_pool`，`backend/market.py` 聚合；Vibe API `/api/market/emotion` | `_core.py` `get_zt_pool/get_dt_pool/get_zb_pool`，`evidence.py` M3/M4 | 已有 | 适配短线情绪聚合口径 | Vibe 已输出连板股清单；young 要作为证据，不能变推荐榜 | 短线情绪 Evidence |
| 短线情绪 | 后端 runtime：`backend/market.py` `_emotion`、`get_short_term_emotion` | `evidence.py` M3/M4 有基础计数与炸板率；无完整连板梯队/晋级率 evidence schema | 部分 | 重写为 young Evidence 模块扩展 | 口径必须注明日期、池来源，避免把空池当零 | 短线情绪 Evidence |
| 成交额榜 | 后端 runtime：`backend/astock.py` `market_turnover_rank`、`backend/market.py` `get_turnover_top` | 无独立榜单；`_core.py` quote 有成交额字段 | 无 | 适配为只读 evidence，不接成建议 | “Top” 容易被误解成推荐；文案必须强调客观榜单 | 短线情绪 Evidence |
| 市场情绪与行业资金 | 后端 runtime：`backend/market.py` `_sentiment`、`_sectors`，依赖 akshare | `_core.py` `get_fund_flow`、板块列表；`evidence.py` M1/M2 | 部分 | 适配 HTTP-only 优先；akshare 作为 rich-source | akshare 是重依赖，不能成为默认路径 | 统一网络层和缓存 v2 |
| 东财限流、防封、代理降级 | 后端 runtime：`backend/astock.py` `em_get` 串行限流、直连优先、代理降级；`gstock.py` push2/push2delay 降级 | `_core.py` 有 `retry_on_recoverable`，但 fetch_json 等未统一走一个东财会话/限流入口 | 部分 | 复用思路，重写为 young 网络层 | 全局 sleep 会拖慢 CLI；需按 host/source 粒度设计 | 统一网络层和缓存 v2 |
| 缓存 v1/v2 | Vibe runtime：模块级 TTL dict、RSS 文件缓存、portfolio 文件缓存 | `_core.py` 文件缓存；`local_store.py` JSON store；`ReportArtifacts` | 已有 v1 | 重写为小型统一缓存接口 | 不能改变现有缓存路径导致用户旧缓存失效 | 统一网络层和缓存 v2 |
| 港股个股 | 后端 runtime：`backend/gstock.py` 东财 search + stock/get + GMAININDICATOR | `_core.py` 新浪、腾讯、东财、东财 clist；`get_single_stock_quote` | 已有 | 适配关键财务指标，不替换 quote fallback | 东财 search 可能混入窝轮/ETF，需精确匹配 | 港美股和全球市场 |
| 美股个股 | 后端 runtime：`backend/gstock.py` 东财 search + stock/get + GMAININDICATOR | `_core.py` 新浪、腾讯、东财、东财 clist；Yahoo history adapter | 已有 | 适配关键财务指标和 search | 东财美股市场前缀 105/106/107 需验证 | 港美股和全球市场 |
| 韩股 | 后端 runtime：`backend/gstock.py` 支持 `.KS/.KQ/.KR` 搜索与行情；前端文档也声明 | young 无 | 无 | 暂放弃 | 超出 young 当前市场边界，增加 symbol 解析复杂度 | 港美股和全球市场 |
| 全球指数 | 后端 runtime：`backend/gstock.py` 道指、标普、纳指、恒指、恒生科技 | `_core.py` `run_global_market`，A/HK/US 指数 | 已有 | 选择性适配东财 push2delay 降级 | 指数 secid 映射需维护 | 港美股和全球市场 |
| 研报列表与 PDF 链接 | 后端 runtime：`backend/astock.py` `eastmoney_reports`；API `/api/reports` | young 无正式研报端点；`research_bridge.py` 可选外部摘录 | 部分 | 适配为 Evidence，不直接下载 PDF | 研报评级/目标价不能直接变建议；PDF 下载可能触发 403 | A 股扩展数据 |
| 行业研报 | Skill-only：`a-stock-data/SKILL.md` `eastmoney_industry_reports`；Vibe backend 未接 API | young 无 | 无 | 后续再评估 | 文档声明不等于 runtime，先不纳入阶段 1 | 资讯雷达 |
| 公告 | 后端 runtime：`backend/astock.py` `announcements`，`disclosure`；API `/api/announcements`、`/api/disclosure` | `sources/registry.py` 声明 cninfo/hkexnews official，但 adapters 标 unavailable；`sources/extras.py` rich-source 事件尝试 akshare | 有 registry 骨架 | 适配东财公告 HTTP；cninfo 保留 official 后续 | 公告正文和列表时间口径要保留来源 | A 股扩展数据 |
| 财务摘要/估值分位 | 后端 runtime：`financials`、`valuation_percentile`、`full_valuation`；部分依赖 akshare | young `sources/extras.py` rich-source 财务趋势；`reports.py` 只做持仓收益和行情建议 | 部分 | rich-source 适配，不默认 | akshare 重依赖；估值口径可能诱导评分 | A 股扩展数据 |
| 融资融券 | 后端 runtime：`backend/astock.py` `margin_trading`；API `/api/margin` | young 无正式端点；registry 声明 akshare financial/events | 无 | 适配东财 datacenter HTTP | 字段为元，展示需单位明确 | A 股扩展数据 |
| 龙虎榜 | 后端 runtime：`dragon_tiger_board`；API `/api/dragon-tiger` | `sources/extras.py` `fetch_lhb`；CLI `young lhb` | 已有 | 适配席位细节，保留现有 lhb 命令 | 龙虎榜容易被当强势名单，文案要克制 | A 股扩展数据 |
| 大宗交易 | 后端 runtime：`block_trade`；API `/api/block-trade` | `_core.py` `fetch_block_trades`、`run_block_trades_report`；stock evidence optional section | 已有 | 复用 young，实现字段补齐即可 | reportName 字段变动 | A 股扩展数据 |
| 股东户数/分红/解禁 | 后端 runtime：`holder_num_change`、`dividend_history`、`lockup_expiry` | young 无正式 evidence | 无 | 适配为 optional evidence | 季度/事件数据日期不能混成当日行情 | A 股扩展数据 |
| 概念板块归属/热门概念/互动易 | 后端 runtime：`concept_blocks`、`hot_concepts`、`investor_qa` | young profile 自动分类有轻量规则；无接口 | 部分 | 适配概念归属；热门概念谨慎 | 热门概念/问答噪声高，需要去重和证据日期 | A 股扩展数据 |
| ETF 期权 | Skill-only：`a-stock-data/SKILL.md`；Vibe backend 未接 API | young 无 | 无 | 放弃本轮 | 重型、专业且偏交易；超出轻量投研 cockpit | 不进入当前 roadmap |
| 全市场龙虎榜 | Skill-only：`a-stock-data/SKILL.md`；Vibe backend 未接 API | young 无 | 无 | 暂放弃 | 带强名单倾向，不符合当前边界 | 不进入当前 roadmap |
| RSS 资讯雷达 | 后端 runtime：`backend/newsradar.py`，`news_sources.json`，API `/api/radar`、`/api/radar/refresh` | `_core.py` 个股新闻链，`research_bridge.py` 外部研究桥；无赛道 RSS radar | 部分 | 适配为只读资讯聚合，不直接喂模型 | 源数量大；需要去重、红线过滤、缓存、超时 | 资讯雷达 |
| 个股新闻链 | 后端 runtime：Vibe chat tools `query_news` 调 astock news；API `/api/news` 需 akshare | `_core.py` futu、futu feed、新浪滚动、东财快讯组合去重 | 已有 | 复用 young；只参考 Vibe 公告/研报补充 | 不要引入必须 akshare 的默认新闻路径 | 资讯雷达 |
| API 模型配置 | 后端 runtime：`backend/app.py` 请求体 `LLMConfig`；`backend/chat.py` OpenAI-compatible；前端本地保存 | `config.py`、`llm.py`、CLI `config models` | 已有 | 适配 provider 列表和模型发现思路 | Vibe 前端存 key 的模式不适合 CLI 配置 | Model Transport 与本机订阅 CLI |
| 本机订阅 CLI | 后端 runtime：`backend/cli_runtime.py` 支持 `cli-claude`、`cli-qwen`、`cli-deepseek`、`cli-codex`；前端还列出部分 coming soon | young 无等价 model transport；`research_bridge.py` 可配置外部命令但不是模型传输 | 部分 | 重写为独立 Model Transport | 只能本机运行；CLI 无 function calling；超时和工具权限需严控 | Model Transport 与本机订阅 CLI |
| LLM fallback | Vibe runtime：API 接入没有多模型 fallback；CLI 接入按 provider 调本机命令 | `llm.py` 支持 fallback_models、重试、鉴权错误不 fallback | 已有 | 保留 young | 不要用 Vibe 覆盖现有错误分类 | Model Transport 与本机订阅 CLI |
| Chat function calling | Vibe runtime：`backend/chat.py` 5 个工具，API 模式模型可调工具；CLI 模式无 function calling | `chat.py` slash command + LLM 问答 + optional research bridge；不暴露数据工具给模型调用 | 已有不同形态 | 暂不照搬；只借鉴安全边界 | function calling 会扩大数据面，需先完成 Evidence 管道 | Chat 后续另立阶段 |
| MCP | 后端 runtime：`backend/mcp_server.py` 只读 JSON-RPC，暴露 `chat.TOOLS` 的 5 个工具 | young 无 MCP | 无 | 适配只读 MCP，不能当模型供应商 | MCP 工具太少；若扩展需权限和只读保证 | 只读 MCP |
| 测试体系 | Vibe backend 有 FastAPI TestClient、离线修复回归、live 测试；前端未重点核实测试 | young 有 pytest 覆盖 CLI、core、LLM、Evidence、Lens、Chat、PDF、docs | 已有 | 复用 young 测试风格；迁移离线 shape tests | live tests 不能进默认 CI | `_core.py` 渐进重构和总体验收 |

## 核实出的事实差异

- Vibe 文档说 MCP 与全量 A 股工具同源，但实际 `backend/mcp_server.py` 只暴露 5 个 Chat 工具：A 股行情、估值、研报、新闻、全球个股。
- Vibe `a-stock-data/SKILL.md` 声明 40 个端点和 ETF 期权等能力，但 Vibe 后端只接入其中一部分；ETF 期权、全市场龙虎榜、行业研报等没有 FastAPI runtime 路由。
- Vibe README 强调“行情 + 研报只需 requests”，但 `backend/requirements.txt` 默认列入 `akshare`、`mootdx`、`pandas`；代码层是惰性导入/501 降级，不是轻依赖默认安装。
- Vibe `market.py` 注释曾写短线情绪零个股名，但当前 runtime 已返回 `lianban_stocks` 客观榜单。
- young 的 M7 不是 Evidence Bundle 的采集模块；当前 Evidence Bundle 是 M1-M6 加可选 `STOCK`/`FUND`，M7 在 LLM 报告结构、Lens 和委员会约束中体现。
