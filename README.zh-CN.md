# young-stock-cli 中文说明

[![English](https://img.shields.io/badge/README-English-0969da.svg)](README.md)
[![PyPI](https://img.shields.io/pypi/v/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![Python](https://img.shields.io/pypi/pyversions/young-stock-cli.svg)](https://pypi.org/project/young-stock-cli/)
[![CI](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/AdvancingTitans/young-stock-cli/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/young-stock-cli.svg)](LICENSE)

> 终端里的个人投研驾驶舱。

![young-stock-cli 封面](docs/images/cover.png)

`young-stock-cli 0.3.16` 把 A 股、港股、美股、基金、自选持仓、Evidence report 和本地投研流程收进一个 CLI。默认走确定性数据路径；只有显式传入 `--llm` 才会进入模型辅助研究。

需要 Python 3.9+。

```bash
uv tool install young-stock-cli
young init
young daily --format summary
young stock 600519 --llm --lens buffett
young report
```

## 为什么使用

- 一个 CLI 覆盖市场快照、个股研究、基金、自选持仓、报告保存、PDF 导出和飞书发送。
- Evidence 优先：缺失数据保持缺失，不伪装成零。
- 成本边界明确：慢速数据源、browser fallback 和 LLM 调用都需要显式开启。
- 日期与来源可追踪：保留 `requested_date`、`as_of`、source URL、stale、warning 和 missing fields。
- Profile、组合草稿、chat memory、style、diary、cache 与配置均以本地状态为主。
- 提供 read-only MCP，让外部 agent 获取结构化 Evidence，而不是解析终端文本。

## 0.3.16 更新重点

- 新增彼此解耦的 Evidence、Provider、Model Transport、cache、global market、News Radar、Source Adapter 与 read-only MCP 模块。
- Evidence Bundle 有稳定版本契约，并保留 provenance 与 `full`、`degraded`、`simplified` 完整度范围。
- 补充 A 股、港股、美股、基金、精选资讯和客观短线情绪 Evidence。
- 历史日期请求会在访问仅支持实时数据的榜单前被拒绝，避免把实时数据误标成历史数据。
- report review gate 会对证据外数字或日期修复一次；仍无法 grounding 时拒绝输出。
- Profile 使用 atomic write、last-known-good backup 和损坏恢复；无有效备份时拒绝破坏性覆盖。
- CI 与发布流程增加 lint、测试、覆盖率、构建、tag/version 和 wheel smoke test 门禁。

## 常用流程

| 目标 | 命令 |
| --- | --- |
| 快速查看市场和自选持仓 | `young daily --format summary` |
| 生成完整 Evidence report | `young daily --llm` |
| 使用研究委员会视角 | `young daily --llm --lens all --debate-rounds 3` |
| 深入研究单只股票 | `young stock <symbol> --llm --rich-source` |
| 深入研究一只基金 | `young fund <code> --llm --rich-source` |
| 预览并发送最新报告 | `young send --dry-run`，确认后运行 `young send --yes` |
| 检查数据源、模型、PDF 与渠道 | `young diagnose --json` |

`--rich-source` 可能访问较慢的补充来源。`--browser-fallback` 只在已经实现该能力的命令上可用：`young a`、`young stock`、`young fund` 和 `young daily`。

## 产品边界与保证

`young-stock-cli` 是独立项目，安装、配置、cache、Profile、CLI、MCP 和发布周期均由自身维护，不需要配套 runtime。

- 普通 `young daily`、`young stock <symbol>` 和 `young fund <code>` 使用确定性数据路径。
- `--llm` 才开启模型辅助分析；`--lens` 必须与 `--llm` 同时使用。
- 非默认 `--debate-rounds` 只允许与 `--llm --lens all` 同时使用。
- `young report` 只导出已经保存的报告，不会暗中重新运行模型。
- `young send` 没有安全参数时会拒绝执行；`--dry-run` 用于预览，`--yes` 才会发送。
- `full`、`degraded`、`simplified` 表示 Evidence 完整度，不是投资评级。
- mechanical review gate 用于拦截明显的证据外陈述和危险措辞，不等于事实审计、投顾认证或收益保证。
- 不连接券商、不下单、不自动交易。

## 命令矩阵

| 范围 | 命令 | 说明 |
| --- | --- | --- |
| 市场 | `young a`、`young hk`、`young us`、`young global`、`young indices`、`young zt-pool`、`young flow` | 公共市场快照与资金流。 |
| 标的 | `young stock <symbol>`、`young lhb <symbol>`、`young fund <code>`、`young news <query>` | stock 与 fund 需要显式加 `--llm` 才进入模型分析。 |
| 自选日报 | `young daily --format full|summary|key-points`、`young daily --llm` | 支持自定义模块顺序、Lens、rich source 与 browser fallback。 |
| 本地状态 | `young profile ...`、`young portfolio ...`、`young memory ...`、`young style ...`、`young diary ...` | 保存到 young home 目录。 |
| 报告与发送 | `young report`、`young send --dry-run`、`young send --yes` | PDF 是 optional extra；远程发送必须确认。 |
| 配置与支持 | `young config ...`、`young init`、`young diagnose`、`young cache-clear` | 管理模型、渠道、路径、健康状态与 cache。 |
| 交互接口 | `young chat`、`young mcp` | 交互式 chat 与 read-only stdio MCP。 |
| 维护 | `young guide`、`young example`、`young update`、`young uninstall` | 与安装方式一致的维护命令。 |

CLI 没有全局 JSON 开关。`young diagnose --json` 是明确的 machine-readable 诊断入口；结构化投研数据主要通过 MCP 暴露。

## Evidence 与数据语义

### Evidence Bundle

稳定顶层契约包含 `schema_version`、`modules` 和 `_meta`。行情和报告事实可保留 `requested_date`、`as_of`、`source_url`、quality flags、notes、completeness、stale、missing fields 与 warnings。

Daily Evidence 使用 M1-M6 采集模块。Stock Evidence 在此基础上加入 quote、资金流、大宗交易、资讯、A 股扩展 Evidence 或港美股 global-market 数据。Fund Evidence 加入估值、净值日期、基金画像、持仓、持仓行情与精选持仓资讯。

完整度范围来自实际可用模块：

- `full`：quality score 不低于 80。
- `degraded`：quality score 不低于 60。
- `simplified`：覆盖更低，报告必须收窄结论。

这些值只描述 Evidence pack，不描述市场方向或资产质量。

### Source 与 fallback

1. 优先尝试稳定的公共 HTTP 数据源。
2. `--rich-source` 开启较慢的 optional source 与 library-backed extension。
3. `--browser-fallback` 仅在支持它的命令上启用 browser。
4. optional source 失败时省略或标记 unavailable，不用猜测值代替。

Source registry 是候选能力目录，不代表每个来源都已启用。browser、library、search 和 slow source 只有在对应 policy 允许时才参与请求。

Managed HTTP 按 domain 控制并发、最小间隔、retry/backoff、fallback domain、403 circuit breaker 和 429 `Retry-After`，trace 会脱敏。这些机制提升韧性，但不保证第三方服务始终可用。

港美股历史行情可能返回请求日当天或之后第一个可用收盘，并不保证精确命中请求日；未来日期会被拒绝。News cache validator 支持 HTTP 304，但网络失败不会被包装成实时资讯。

### News Radar

News Radar 读取经过治理的 RSS/Atom source，使用 conditional cache header，清洗去重、过滤相关性、聚合同一事件，并在送入模型前压缩。source、URL、发布时间、标题、事件分组和截断状态仍可审查。

## Daily 投研框架：M1-M7

| 模块 | 回答的问题 |
| --- | --- |
| M1 大盘指数与市场广度 | 市场整体偏强、偏弱还是分化？ |
| M2 板块强弱与资金流 | 资金流向哪里？ |
| M3 赚钱效应与涨停结构 | 正反馈是否广泛且可持续？ |
| M4 下跌与炸板风险 | 风险释放是否扩大？ |
| M5 持仓与市场风格 | 当前环境是否支持自选持仓？ |
| M6 抗跌方向 | 哪些方向相对更稳？ |
| M7 研究委员会综合判断 | 只在 `--lens all` 下生成。 |

单 Lens 不会触发隐藏辩论，也不会生成 M7。`--lens all` 只把委员会共识、分歧、看多 Evidence、看空 Evidence 和待验证问题压缩成条件化研究结论。任何角色都不能执行交易。

## Investor Lens 与 Method cards

`balanced` 是默认 style。`young style` 与 `/style` 使用同一份 registry。

| Lens | 关注点 |
| --- | --- |
| `buffett` | 质量、护城河、资本配置、安全边际 |
| `munger` | 多元思维、反向思考、激励机制 |
| `graham` | 资产负债表、稳定性、下行保护 |
| `klarman` | 复杂性折价、催化剂、永久损失控制 |
| `lynch` | 可理解的增长与盈利兑现 |
| `o_neil` | 盈利加速、龙头、量价确认 |
| `wood` | 颠覆式创新与长期渗透率 |
| `dalio` | 宏观周期、分散化、风险平衡 |
| `soros` | 反身性、预期差、政策拐点 |
| `livermore` | 趋势、关键点、严格风险控制 |
| `minervini` | 趋势模板、强势股、波动收缩 |
| `simons` | 可检验信号、样本外稳健性、成本 |
| `duan_yongping` | 商业模式、文化、长期现金创造 |
| `zhang_kun` | 高质量商业模式与自由现金流 |
| `feng_liu` | 市场认知、赔率、反转、边际变化 |

使用 `young style list`、`young style show`、`young style set <name>`、`young style clear` 或 `/style list|set|show|clear`。

Method cards 用于约束报告结构，不是评分：

- 估值：`DCF-lite`、`Reverse DCF`、`Comps`、`LBO-lite`、`3-statement-lite`、`SOTP-lite`。
- 研究：财报解读、业绩前瞻、催化剂日历、投资逻辑追踪、行业综述、新闻归因、持仓风险复盘。
- 决策：`IC Memo`、`Due Diligence checklist`、`Porter Five Forces`、`Unit Economics`、`VCP`、`Rebalancing Review`。

## Profile、portfolio、memory 与 diary

Profile 为 daily report 提供真实自选列表。股票条目可保留可解释的 market、asset type、category、evidence、buy date 与 quantity。

```bash
young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100
young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000
young profile list
young profile remove-stock 600519
young profile clear
```

Profile 是本地明文 JSON，不是 encrypted credential store。写入采用 atomic replace 与 `.bak` 恢复；文件损坏且无法恢复时会明确报错，不会静默覆盖。

Portfolio 是轻量的本地实验区：

```bash
young portfolio create core
young portfolio add core 600519 100
young portfolio show core
```

`young portfolio compare` 目前只输出 roadmap 提示，尚未执行真实历史比较。

- `young memory show|list|clear|reset` 管理长期 chat memory。
- `young diary save <date> --text ...` 与 `young diary show <date>` 管理 diary snapshot。

## 模型配置

`young config models` 是正式的模型配置入口。配置 schema v2 位于 `$YOUNG_STOCK_HOME/config.json`；未设置该环境变量时默认使用 `~/.young_stock`。

支持两种 Model Transport：

- `api`：API Provider 与 optional fallback model。
- `subscription-cli`：本机已安装并登录的 `codex` 或 `claude` CLI。

运行 `young config providers` 查看当前 API Provider registry。它包含主要 hosted provider、Ollama，以及用于自定义 chat-completions endpoint 的显式 `openai-compatible` 选项。自动化脚本不应复制 README 中的静态列表。

```bash
export OPENAI_API_KEY="..."
young config models --provider openai --model gpt-4.1 --api-key-env OPENAI_API_KEY
young config models --provider ollama --model llama3.1 --api-base http://localhost:11434/v1
young config models --provider openai-compatible --api-base https://example.com/v1 --model <model-id> --api-key-env MODEL_API_KEY
young config models --list
young config show
young config path
```

保存 API model 时必须指定 `--model`。`--list` 会探测可用于 chat 的候选 model，因此可能比直接请求 model list 更慢。只支持 coding task 的 endpoint 会被拒绝用于投研或 chat。

使用 `young config models ... --fallback-model X --fallback-model Y` 配置 fallback。只有 rate limit、quota、瞬时服务错误或明确 model unavailable 时才轮换；认证与错误 base URL 不触发轮换。

通过 `--api-key-env` 提供的 key 只在内存中解析，不会复制到本地配置。`young config show` 会遮蔽 secret。

`subscription-cli` 会在临时空目录启动本地 subprocess，通过 standard input 传入已经构造好的 Evidence 与 prompt，设置 timeout，并在失败时终止 process group。它不支持远程 model list；使用前需要先安装并登录对应本机 CLI。

## MCP 与 chat

`young mcp` 启动 read-only stdio MCP server，提供 quote、indices、market emotion、daily/stock/fund Evidence、news、announcement、research report、fund flow 和 source health 等结构化工具。

MCP 不调用模型、不保存配置、不发送消息、不修改 Profile、memory、diary 或 cache，也不提供交易操作。

`young chat` 同时支持本地 slash command 与普通模型对话。底层 Click command 可独立完成的本地或确定性 slash 查询不需要模型；普通消息需要先配置 Model Transport。chat 会阻止高风险维护和配置流程，并限制 Profile 与 memory 操作。

| CLI | Chat slash |
| --- | --- |
| `young a` | `/a` |
| `young stock <symbol> [--llm] [--lens ...]` | `/stock <symbol> [--llm] [--lens ...]` |
| `young fund <code> [--llm] [--lens ...]` | `/fund <code> [--llm] [--lens ...]` |
| `young daily [--llm] [--lens ...]` | `/daily [--llm] [--lens ...]` |
| `young news <query>` | `/news <query>` |
| `young report` | `/report` |
| `young send --dry-run|--yes` | `/send --dry-run|--yes` |
| `young profile list` | `/profile list` |
| `young memory show` | `/memory show` |
| `young style list|set|show|clear` | `/style list|set|show|clear` |
| `young diagnose` | `/diagnose` |

chat 另有 `/help`、`/clear` 和 `/exit`。配置、安装、portfolio、diary、update、uninstall 与 cache maintenance 保留在 CLI 侧。

## 报告与发送

安装 PDF extra 后，`young report` 可以把最新 Markdown 导出为 PDF。`young send --dry-run` 预览最终解析出的 Markdown/PDF bundle 与渠道；`young send --yes` 才执行远程发送。直接调用 `young send` 而不提供任何一个安全参数会被拒绝。

`young config channel add|list|remove` 管理发送渠道。飞书支持 webhook 与 app credential 两种模式。

## 安装、更新与卸载

选择一种安装方式后，建议持续使用同一组命令。

### uv tool

```bash
uv tool install young-stock-cli
uv tool install --upgrade young-stock-cli
uv tool install --force 'young-stock-cli'
uv tool install --upgrade 'young-stock-cli[pdf]'
# 从当前 repository checkout 安装：
uv tool install --force '.[pdf]'
uv tool uninstall young-stock-cli
```

### pip

```bash
python3 -m pip install --upgrade young-stock-cli
python3 -m pip install --upgrade 'young-stock-cli[pdf]'
python3 -m pip uninstall -y young-stock-cli
```

对应 helper 是 `young update` 与 `young uninstall`。PDF 导出使用 optional `weasyprint` extra；base install 保持为 `requests`、`rich`、`click` 与 `prompt-toolkit`。

## 诊断、隐私与排查

- `young diagnose` 是 read-only；`young diagnose --json` 适合接入 support tooling。
- 本地状态位于 `$YOUNG_STOCK_HOME` 或 `~/.young_stock`，默认不会上传。
- API key 可以留在环境变量中，显示配置时会被遮蔽。
- rich source 与 browser fallback 只有显式请求时才运行。
- 报告数据源问题前先运行 diagnose。
- 数据看似过期时，先比较 `requested_date`、`as_of`、stale、source 与 warning。
- 普通 CI 排除标记为 `network` 的测试；live check 必须显式执行。

## 截图与素材

| 素材 | 文件 |
| --- | --- |
| 封面 | `docs/images/cover.png` |
| 指数演示 | `docs/images/demo-indices.png` |
| 涨停池演示 | `docs/images/demo-zt-pool.png` |

![指数演示](docs/images/demo-indices.png)
![涨停池演示](docs/images/demo-zt-pool.png)

## License

MIT，详见 [LICENSE](LICENSE)。
