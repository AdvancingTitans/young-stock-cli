# Architecture Decisions

## 已确认决策

1. 使用 Adapter 接入能力，不整体嵌入 Vibe。

   理由：young 已有 SourceResult、Resolver、Evidence Bundle、CLI 与报告约束。整体并入 Vibe 的 FastAPI/React 会改变产品形态和依赖边界。

2. 保留 young 的 SourceResult、Resolver 和 Evidence Bundle。

   理由：这些抽象已经覆盖源选择、失败记录、健康检查、M1-M6 证据组织和 LLM 输入约束。Vibe 的实现是可参考的数据函数，不是替代架构。

3. API 供应商与模型传输方式分离。

   理由：API provider、OpenAI-compatible endpoint、本机订阅 CLI 是不同 transport。配置层不能把 provider 与 transport 混成一个不可扩展字段。

4. MCP 是外部只读接口，不是模型供应商。

   理由：MCP 用于给外部工具调用 young 数据能力；它不提供模型调用、不应影响 `young config models`。

5. 资讯必须先去重和聚合再进入模型。

   理由：RSS 和新闻源噪声高、重复多、时间粒度不同。直接塞给模型会放大幻觉和来源混淆。

6. 短线情绪是证据，不直接生成买卖信号。

   理由：连板、炸板、成交额榜属于公开市场状态，可进入 M3/M4 作为风险和赚钱效应证据；不能变成推荐、预测或交易触发器。

7. `_core.py` 只做渐进迁移，不进行一次性重写。

   理由：`_core.py` 承载大量已经被 CLI 和测试覆盖的行为。一次性重写风险高，且不符合本阶段“只核实、建记忆、不实现正式功能”的边界。

8. 重型依赖保持可选。

   理由：Vibe 中 akshare/mootdx/pandas 可支撑部分数据，但 young 的默认路径要尽量保持轻量、可安装、可运行。

9. 缺失、空结果和错误必须保留语义。

   理由：投资研究输出要求证据可追踪。空池、接口失败、未披露、历史不可得是不同状态，不能统一写成 0。

10. Vibe 的分析框架只可作为参考，不替换 young M1-M7。

    理由：young 的报告、review gate、Lens 和 committee 已围绕 M1-M7 建立约束；替换框架会破坏用户已有使用预期。

11. LLM API Provider Registry 独立于数据源 registry。

    理由：本阶段的 provider 指模型 API 供应商，不是行情/资讯数据源。LLM provider 需要描述协议、API base、key env、模型列表路径、chat 路径和模型探测能力；数据源仍由 `sources/*` 后续阶段处理。

12. `openai-compatible` 作为显式 provider，而不是把任意兼容端点记录为 `openai`。

    理由：兼容协议不等于 OpenAI 官方服务。显式 provider 能避免配置含义混淆，并要求用户同时给出 Base URL 和模型。

13. 不维护易过期的具体模型清单。

    理由：模型 ID 更新频繁。young 只保存 provider 结构和模型列表解析规则；可用模型通过服务端 `/models` 与可选 chat 探测确认。

14. Model Transport 使用独立 registry，不并入 API Provider Registry。

    理由：API provider 描述远端协议、Base URL、模型列表和鉴权；transport 描述调用路径。`api` transport 复用阶段 1 的 Provider Registry；`subscription-cli` transport 只负责本机已登录 CLI 的非交互调用。

15. 本机订阅 CLI 只登记当前环境能验证命令形态的 OpenAI local CLI 和 Claude Code。

    理由：当前环境可验证 `codex --version` / `codex exec --help` 与 `claude --version` / `claude --help`。Gemini CLI、Qwen Code、DeepSeek CLI 未在当前环境可靠验证，不能只凭命令名称或文档想象声明支持。

16. Subscription CLI transport 在临时空目录中运行，且不开放数据源或仓库工具。

    理由：本阶段 CLI 只接收 young 已构造好的 Evidence 和 Prompt。实现层通过 stdin 输入、超时、进程组终止、临时目录清理、stderr 诊断和禁用高权限参数降低越界风险；不会让模型自行读取项目、修改代码、抓取行情或修改 Profile。
