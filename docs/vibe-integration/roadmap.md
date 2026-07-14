# Vibe Integration Roadmap

本路线图只描述后续阶段，不代表本阶段已实现正式功能。所有阶段默认不改变公开 CLI 行为，除非该阶段验收标准明确要求并另行评审。

## 1. Provider Registry 与 API 供应商扩展

状态：完成（2026-07-08）。

目标：
将 young 当前分散在 CLI 和 `LLMClient` 中的 LLM API 供应商硬编码，收敛为统一 Provider Registry。保留现有模型列表查询、文本模型过滤、最小调用验证、fallback models、重试、错误分类和 Anthropic 独立协议。

范围：
新增 `src/young_stock/providers.py`；登记 `openai`、`xai`、`ark`、`kimi`、`moonshot`、`deepseek`、`qwen`、`ollama`、`anthropic`、`siliconflow`、`minimax`、`openrouter`、`groq`、`together`、`openai-compatible`；CLI provider choice 从注册表动态生成；新增 `young config providers`；模型列表过滤兼容 `data`、`models`、`modalities`、`input_modalities`、`output_modalities`。

非目标：
不接订阅 CLI；不接数据源；不接 MCP；不改报告结构；不增加跨供应商隐式 fallback；不实现 Model Transport。

实际修改模块：
`src/young_stock/providers.py`、`src/young_stock/llm.py`、`src/young_stock/cli.py`、`tests/test_provider_registry.py`、`tests/test_openai_compatible_provider.py`、`tests/test_model_listing.py`、`tests/test_provider_cli.py`。

验收标准：
旧配置继续可用；现有 `young config models` 参数继续可用；`openai-compatible` 必须显式配置 Base URL 和模型；Anthropic 继续走 messages 协议；认证、限流、模型不存在和网络错误分类保持；secret 不出现在 CLI 输出或错误信息中。

验收结果：
通过新增 provider 测试与现有 LLM/config/CLI 回归测试。未实现订阅 CLI、数据源、MCP 或报告结构改造。

## 2. Model Transport 与本机订阅 CLI

状态：完成（2026-07-08）。

目标：
把 API provider 与模型传输方式分离，为本机已登录 CLI 模型接入预留接口。

范围：
新增 transport 抽象；保留现有 OpenAI-compatible/Anthropic client；调研本机 CLI 可执行探测、超时、纯文本输出和安全限制。

非目标：
不让 CLI transport 执行数据工具；不保存第三方登录态；不改变 `young config models` 当前行为。

预计修改模块：
`src/young_stock/llm.py`、`src/young_stock/config.py`、`src/young_stock/cli.py`、`tests/test_llm.py`、`tests/test_config.py`。

验收标准：
现有 API provider 测试不回退；transport 错误信息明确；CLI transport 在未安装时返回可理解错误；认证错误不触发模型 fallback。

实际修改模块：
`src/young_stock/model_transport/base.py`、`api.py`、`subscription_cli.py`、`registry.py`、`src/young_stock/config.py`、`src/young_stock/cli.py`、`src/young_stock/chat.py`、`src/young_stock/reports.py`、`tests/test_model_transport.py`、以及少量既有 config/provider CLI 测试期望更新。

验收结果：
旧配置自动迁移为 `transport=api`；`daily`、`stock`、`fund`、`chat` 的模型调用通过 transport registry；APITransport 复用阶段 1 的 `LLMClient` 和 Provider Registry；SubscriptionCliTransport 支持当前环境可验证的 OpenAI local CLI 与 Claude Code，并覆盖 fake CLI 的成功、未安装、无法验证、未登录、超时、非零退出、空输出、stderr、进程组终止、临时目录清理和旧配置迁移测试。报告 Metadata 保存 `transport`、`provider`、`model` 和 usage，不保存 API Key、Authorization Header 或临时路径。

## 3. 统一网络层和缓存 v2

状态：完成（2026-07-08）。

目标：
统一 HTTP 请求、东财限流、直连/代理策略、重试和缓存元数据。

范围：
抽出小型网络 helper；按 host/source 限流；缓存记录 source、as_of、requested_date、ttl 和 unavailable 语义。

非目标：
不一次性重写 `_core.py`；不改变缓存目录结构，除非提供兼容读取。

预计修改模块：
`src/young_stock/_core.py`、`src/young_stock/market_routes.py`、`src/young_stock/sources/*`、`tests/test_core.py`、`tests/test_market_routes.py`。

验收标准：
东财请求可串行限流；空/错误响应不被当成有效缓存；缺失值保持 None 或 unavailable；localhost 请求测试不受系统代理影响。

## 4. 短线情绪 Evidence

状态：完成（2026-07-08）。

目标：
把连板梯队、最高连板、炸板率、封板率、晋级率和成交额榜作为 Evidence，而非买卖信号。

范围：
扩展 daily evidence 的 M3/M4；新增 source/date/口径字段；可选加入成交额榜事实清单。

非目标：
不生成强势股推荐；不生成主观热度评分；不改变 M1-M7 顺序。

预计修改模块：
`src/young_stock/evidence.py`、`src/young_stock/_core.py`、`src/young_stock/reports.py`、`tests/test_evidence.py`、`tests/test_llm_reports.py`。

验收标准：
空池不伪装成 0；榜单文案标注客观公开榜单；LLM 报告只可引用证据和日期；默认 deterministic daily 不调用模型。

实际修改模块：
`src/young_stock/evidence/__init__.py`、`src/young_stock/evidence/emotion.py`、`src/young_stock/reports.py`、`src/young_stock/research_style.py`、`src/young_stock/review_gate.py`、`tests/test_emotion_evidence.py`、`docs/vibe-integration/progress.md`。

验收结果：
短线情绪仅复用已有涨停、跌停和炸板池；晋级率按昨日涨停代码集合与今日二板以上代码集合的交集计算，并保存分子和分母。缺失字段保持 `None` 或 `missing_fields`，空池与缺失分开处理，节假日前一交易日回退使用真实 `as_of`。M1-M6 已接入客观证据，M7 只使用压缩情绪摘要，Review Gate 拦截把情绪直接写成买入、卖出或仓位信号的表达。

## 5. A 股扩展数据

状态：部分完成（2026-07-08）。

目标：
补齐公告、研报、融资融券、股东户数、分红、解禁、概念归属、互动问答等只读证据。

范围：
优先接 HTTP-only 东财 datacenter 和公告列表；akshare/mootdx 保留 rich-source 或放弃；接入 stock/fund evidence 的 optional sections。

非目标：
不接 ETF 期权；不接全市场龙虎榜；不做批量筛选。

预计修改模块：
`src/young_stock/sources/extras.py`、`src/young_stock/evidence.py`、`src/young_stock/cli.py`、`tests/test_stock_extras.py`、`tests/test_cli.py`。

验收标准：
所有扩展字段有 source/date；HTTP 错误不阻断基础行情；rich-source 缺依赖时提示清楚；报告不把研报评级当结论。

实际修改模块：
`src/young_stock/sources/adapters/eastmoney_base.py`、`eastmoney_capital.py`、`eastmoney_market.py`、`eastmoney_reports.py`、`cninfo.py`、`ths.py`、`mootdx.py`、`a_share_extensions.py`、`src/young_stock/_core.py`、`src/young_stock/evidence/__init__.py`、`tests/test_a_share_adapters.py`、`tests/test_stock_extras.py`。

验收结果：
公告、研报、融资融券、股东户数、分红、限售解禁、概念/行业归属、个股/行业/概念资金流、大宗交易、龙虎榜已进入只读 Evidence。`_core.fetch_a_share_extensions()` 已缩为兼容入口，实际聚合迁入 Adapter 包。互动问答、PDF 研报全文、完整财务三表、一致预期、逐笔和五档仍为 `--rich-source` 跳过项，未写成完成。

## 6. 港美股和全球市场

状态：部分完成（2026-07-08）。

目标：
增强港美股 quote 之外的关键财务指标和全球指数降级能力。

范围：
参考 Vibe `gstock.py` 的东财 search、GMAININDICATOR、push2delay 降级；保留 young 现有新浪/腾讯/东财 quote 链。

非目标：
不默认支持韩股；不接 Yahoo/SEC/期权全量 Skill-only 能力。

预计修改模块：
`src/young_stock/_core.py`、`src/young_stock/sources/adapters.py`、`src/young_stock/evidence.py`、`tests/test_source_adapters.py`、`tests/test_core.py`。

验收标准：
现有港美股 quote 测试通过；关键指标缺失时不报错；东财 search 精确代码优先；指数降级不降低数据日期可追踪性。

实际修改模块：
`src/young_stock/global_market.py`、`src/young_stock/_core.py`、`src/young_stock/evidence/__init__.py`、`tests/test_global_market.py`、`tests/test_core.py`。

验收结果：
港股 symbol 统一为五位 `.HK`；quote merge/enrich 使用规范化匹配键，避免不同源四位/五位后缀互相漏匹配。新增轻量 source plan：港美股 quote 为新浪、腾讯、东财；history 为东财、Yahoo；指数按现有港股腾讯优先、美股新浪优先并保留东财兜底。东财候选筛选要求精确代码匹配，并过滤票据、认购认沽、牛熊、杠杆/反向 ETF、ETN、warrant 等相似标的。历史 K 线解析不会返回当前日期之后的数据。全球指数和港美股扩展继续进入既有 Evidence Bundle 的 `STOCK.global_market`，未建立独立分析体系。`--rich-source` 只暴露 SEC 10-K/10-Q/8-K、XBRL、分析师预期、机构持仓、美股期权、完整财务报表的结构化入口或缺依赖提示，不把 SEC Filing 全文传入模型。

## 7. 资讯雷达

状态：完成（2026-07-08）。

目标：
建立行业/赛道 RSS 资讯雷达，先去重和聚合，再作为 Chat/LLM 可选上下文。

范围：
RSS 源配置、抓取、红线过滤、去重、TTL 文件缓存、简洁 CLI 或 evidence 接口。

非目标：
不把原始 100+ RSS 源全部默认抓取；不让模型直接吃未去重原文；不替代个股新闻链。

预计修改模块：
`src/young_stock/research_bridge.py`、新增 `src/young_stock/news_radar.py` 或 sources adapter、`tests/test_research_bridge.py`。

验收标准：
无缓存时返回骨架或明确 unavailable；刷新可超时控制；每条资讯保留 source/url/time；进入模型前已去重和截断。

实际修改模块：
`src/young_stock/data/news_sources.json`、`src/young_stock/news_radar.py`、`src/young_stock/_core.py`、`src/young_stock/evidence/__init__.py`、`src/young_stock/reports.py`、`src/young_stock/research_style.py`、`pyproject.toml`、`tests/test_news_radar.py`、`tests/test_evidence.py`、`tests/test_llm_reports.py`。

验收结果：
来源目录记录名称、URL、赛道、国家/语言、默认启用、可能需要代理和健康状态。抓取复用统一网络层，具备全局并发、单域名并发、ETag、Last-Modified、304、超时、重试、熔断和原子缓存。进入模型前固定执行原始资讯、清洗、Canonical URL、标题/链接去重、同事件多来源聚合、持仓/行业匹配和 Evidence 压缩；缺失来源、异常时间和正文缺失只标记状态，不补事实。普通 daily 只抓宏观、全球市场和持仓相关行业，`--rich-source` 才抓全部赛道；个股 Evidence 只保留公司、所属行业/概念、上下游和明确相关宏观事件。不实现 MCP。

## 8. 只读 MCP

状态：完成（2026-07-08）。

目标：
为外部 agent 暴露 young 的只读数据能力。

范围：
只读工具列表、工具调用、错误包装；默认不启动服务；只返回客观数据。

非目标：
MCP 不是模型供应商；不开放写 profile、send、config、交易等 mutation。

预计修改模块：
新增 `src/young_stock/mcp_server.py` 或插件入口、`src/young_stock/command_registry.py`、`tests/test_mcp.py`。

验收标准：
工具只读；无配置即可列出工具；错误不泄漏 secrets；不会调用 LLM。

实际修改模块：
`src/young_stock/mcp_server.py`、`src/young_stock/cli.py`、`tests/test_mcp.py`、`docs/vibe-integration/progress.md`。

验收结果：
新增 `young mcp` stdio server。工具列表仅包含只读 Evidence 能力：quote、market indices、market emotion、daily/stock/fund evidence、stock news、announcements、research reports、fund flow 和 source health。quote 复用 `SourceResolver`；其余数据工具复用 `build_daily_evidence()`、`build_stock_evidence()`、`build_fund_evidence()` 并只返回 young 标准 Evidence 切片。响应统一包含 requested date、actual as_of、source、stale、missing 和 warnings。未暴露持仓/Profile/Memory/Diary/cache/channel/trading/shell/file 等 mutation 工具。

## 9. `_core.py` 渐进重构和总体验收

状态：部分完成（2026-07-08）。

目标：
把 `_core.py` 中已稳定的网络、缓存、数据解析逐步迁出，降低单文件复杂度。

范围：
按数据域小步移动：HTTP helper、东财 datacenter、quote parse、fund data、news chain；每步保持兼容导出。

非目标：
不一次性重写；不删除现有 public/imported 函数；不改变 CLI 输出。

预计修改模块：
`src/young_stock/_core.py`、新建小模块、全量测试目录。

验收标准：
所有现有测试通过；新增 adapter/evidence 测试覆盖关键缺失值和 fallback；CLI help 与默认行为保持不变；docs/vibe-integration/progress.md 更新验收结果。

验收结果：
只迁移已有 Adapter、fixture/contract/fallback/cache 测试保护的 A 股扩展聚合；`_core.fetch_a_share_extensions()` 保留兼容入口。`_core.py` 仍保留 quote、fund、news、CLI 打印和多数兼容函数，未一次性重写。

## 延期和放弃项

延期：
- 未验证的本机订阅 CLI provider。
- SEC/XBRL/机构持仓/期权等港美 rich-source 真正 adapter。
- CNInfo/HKEX 官方公告正文 adapter。
- SSE/HTTP 形态 MCP transport。
- `_core.py` quote、fund、news chain 的进一步分域拆分。

放弃：
- 韩股默认支持。
- ETF 期权。
- 全市场龙虎榜筛选。
- 把参考项目的 React/FastAPI 架构整体并入 young。
