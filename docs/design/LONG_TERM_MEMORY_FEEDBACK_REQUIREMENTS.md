# 长期记忆与反馈闭环需求文档

## 1. 背景

日期：`2026-03-19`

ACE-Lite 当前主链为：

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

现有系统已经具备以下基础能力：

- `MemoryProvider` V2 合约：`search_compact()` + `fetch()`
- memory stage 的 `temporal filter`、`timeline`、`recency boost`、`namespace`、`postprocess`
- `local_notes`、`profile_store`、`selection_feedback`、`durable preference capture`
- benchmark、summary、regression gate、runtime stats、MCP/CLI 入口

当前缺口不在“是否有 memory 接口”，而在：

- 缺少可持续写入、可时序回放、可评估的长期记忆层
- 缺少面向真实用户问题的结构化问题上报面
- 缺少把开发过程中的 dogfooding 问题快速回流到优化决策的内循环
- 缺少面向长期记忆收益与风险的专门验证闭环

## 2. 目标

本轮需求的目标是把以下四类能力统一到一个可演进的产品与工程闭环中：

1. 长期记忆：让 ACE-Lite 能跨会话沉淀高价值 observation、fact、edge，并在 `ace_plan` 中作为一级检索信号使用。
2. 用户问题上报：让真实使用者能按统一模板提交问题，并能被开发者追踪、归因、转化为 benchmark 与优化任务。
3. 开发内循环反馈：让本地 dogfooding 过程中的失败、降级、手工纠偏能自动或半自动沉淀为开发决策输入。
4. 评估与验证：让长期记忆与反馈系统的收益、噪声、时延、回放稳定性都可度量、可对比、可回归门禁。

## 3. 设计原则

### 3.1 一级能力，不做外挂主逻辑

- 长期记忆应内建到现有 `memory stage` 的一级能力中。
- 不应先做成外挂 MCP 插件或 plugin runtime 旁路主检索逻辑。

### 3.2 保持现有合约稳定

- 不破坏 `MemoryProvider` 的基础契约。
- CLI、MCP、benchmark、schema、replay 的公开 contract 应尽量保持兼容。

### 3.3 local-first 与 deterministic 优先

- 第一版后端优先采用本地 `SQLite + FTS5`。
- 所有检索与写入能力都应支持 `as_of` 或等价时序边界，以避免 replay 漂移和未来信息泄漏。

### 3.4 observation 优先于“直接写事实”

- 原始事件应先记录为 `observation/event`。
- `fact` 应作为可追溯、可 supersede、可过期的派生层。

### 3.5 闭环优于单点功能

- 任何反馈能力都必须能回流到：
  - benchmark case
  - 长期记忆 observation/fact
  - 开发优先级决策
- 不能只做“收集数据”的静态仓库。

### 3.6 2026-03-19 Phase 1 Contract Freeze

- `memory.long_term.*` 第一轮只冻结最小 contract，不提前绑定 store/provider 细节：
  - `enabled`
  - `path`
  - `top_n`
  - `token_budget`
  - `write_enabled`
  - `as_of_enabled`
- 当前默认路径固定为 `context-map/long_term_memory.db`。
- observation/fact 先以独立 schema helper 冻结，不直接改动现有 `memory -> augment` 公开 payload。
- 第一轮强制保留以下边界字段：
  - `repo`
  - `root`
  - `namespace`
  - `user_id`
  - `profile_key`
  - `as_of`
- 第一轮 schema 版本：
  - `long_term_observation_v1`
  - `long_term_fact_v1`

## 4. 范围

### 4.1 In Scope

- 长期记忆存储、provider、capture/ingestion 管线
- 用户问题上报模板、持久化、聚合与开发消费路径
- 开发内循环自动捕获与手动确认能力
- benchmark/summary/regression 的长期记忆与反馈指标扩展
- CLI/MCP/runtime status/doctor 层面的反馈与观测入口

### 4.2 Out of Scope

- 第一版不引入 Neo4j、JanusGraph 等外部图库
- 第一版不做完整 Graphiti 级别 property graph 演化
- 第一版不做复杂 Web UI
- 第一版不让长期记忆直接反向驱动 index/source_plan 的公开 contract 变形

## 5. 需求总览

### 5.1 长期记忆能力

需要新增一条兼容现有 memory contract 的长期记忆链路：

`capture/ingestion -> LongTermMemoryStore -> LongTermMemoryProvider -> memory stage`

要求：

- store 为本地 `SQLite + FTS5`
- provider 实现 `search_compact()` / `fetch()`
- memory stage 可无缝消费长期记忆结果
- 可与现有 `OpenMemoryMemoryProvider`、`LocalNotesProvider`、`SelectionFeedbackStore` 协同
- 支持 `repo`、`root`、`namespace/container_tag`、`user_id`、`profile_key`、`as_of`

### 5.2 用户问题上报能力

需要新增结构化 `issue_report` 能力，用于收集真实用户使用中遇到的问题。

要求：

- 用户可通过 CLI/MCP 提交结构化问题
- 问题模板应包含：
  - `title`
  - `query`
  - `repo`
  - `root`
  - `user_id`
  - `profile_key`
  - `occurred_at`
  - `severity`
  - `category`
  - `expected_behavior`
  - `actual_behavior`
  - `repro_steps`
  - `selected_path`
  - `plan_payload_ref`
  - `attachments`
  - `status`
  - `resolution_note`
- 每条问题应可关联一次具体 plan/run 或 observability snapshot
- 问题应支持后续被标记为 `open/in_review/fixed/rejected`

### 5.3 开发内循环反馈能力

需要把开发者本地使用 ace-lite MCP 时的真实失败与手工修正快速回流到开发决策。

要求：

- 自动捕获：
  - `ace_plan` 失败、超时、降级
  - `evidence_insufficient`
  - `memory_fallback`
  - `noisy_hit`
  - latency budget exceeded
  - 同 query 的连续重试
  - 开发者手工选择与 top candidate 不同的路径
- 手工确认：
  - 开发者可把自动捕获事件提升为 `dev_issue`
  - 开发者可记录 `dev_fix` / `resolution_event`
- 自动捕获事件必须带上：
  - query、repo、root、git/版本快照
  - runtime profile、config fingerprint
  - memory/index/source_plan/validation 的关键 observability 摘要
  - candidate files、selected path、error、trace 引用

### 5.4 评估与验证闭环

需要扩展 benchmark，使长期记忆与反馈系统可量化评估。

要求：

- 支持以下 case 类型：
  - `memory-neutral`
  - `memory-helpful`
  - `memory-harmful-negative-control`
  - `time-sensitive`
  - `cross-session-recovery`
- 支持 lane 对照：
  - `baseline_none`
  - `ltm_readonly_seeded`
  - `ltm_readwrite_sequence`
  - `ltm_ablation`
- 支持时序验证与 `as_of` replay
- 支持把真实问题转 benchmark case

## 6. 建议架构

### 6.1 存储层

第一版建议使用 `context-map/long_term_memory.db` 或等价路径。

推荐核心表：

- `observations`
  - 原始事件：query、plan、validation、feedback、issue_report、dev_issue、dev_fix
- `facts`
  - 从 observations 提炼出的稳定事实
- `triples`
  - 轻量关系边：`subject/predicate/object`
- `retrieval_log`
  - 记录长期记忆的命中、选择与 attribution

可选附加表：

- `issue_reports`
- `issue_links`
- `ingestion_jobs`

### 6.2 Provider 层

新增 `LongTermMemoryProvider`。

要求：

- 对外继续暴露 `search_compact()` / `fetch()`
- 内部支持 observation/fact/triple 的融合检索
- 支持时间边界、namespace、repo 过滤
- 支持图邻域扩展，但第一版仅 1-hop/2-hop 轻量扩展

### 6.3 Capture/Ingestion 层

新增 `LongTermMemoryCaptureService` 或等价 sink。

建议 capture 点：

- `source_plan` 结束后
- `validation` 结束后
- `selection_feedback` 记录时
- `issue_report` 提交时
- `dev_issue` / `dev_fix` 记录时

注意：

- 不把复杂写入逻辑塞进 provider
- 尽量把长耗时抽取放到异步或延迟处理路径

## 7. 数据模型要求

### 7.1 Observation

必须具备：

- `id`
- `kind`
- `repo`
- `root`
- `namespace`
- `user_id`
- `profile_key`
- `query`
- `payload`
- `observed_at`
- `as_of`
- `source_run_id`
- `severity`
- `status`

### 7.2 Fact

必须具备：

- `id`
- `fact_type`
- `subject`
- `predicate`
- `object`
- `confidence`
- `valid_from`
- `valid_to`
- `superseded_by`
- `derived_from_observation_id`

### 7.3 Issue Report

必须具备：

- `issue_id`
- `title`
- `category`
- `severity`
- `status`
- `query`
- `repo`
- `root`
- `user_id`
- `profile_key`
- `expected_behavior`
- `actual_behavior`
- `repro_steps`
- `plan_payload_ref`
- `selected_path`
- `occurred_at`
- `resolved_at`
- `resolution_note`

## 8. 集成点

优先改动位点：

- `src/ace_lite/cli_app/orchestrator_factory.py`
  - 接长期记忆 provider 与反馈 channel
- `src/ace_lite/orchestrator_config.py`
  - 新增 `memory.long_term.*`、`feedback.issue_report.*`、`feedback.dev_loop.*`
- `src/ace_lite/orchestrator.py`
  - 接 capture sink
- `src/ace_lite/pipeline/stages/memory.py`
  - 接长期记忆结果与 attribution 摘要
- `src/ace_lite/mcp_server/service.py`
  - 暴露新 MCP 接口
- `src/ace_lite/mcp_server/server_tool_registration.py`
  - 注册 issue/dev feedback 工具
- `src/ace_lite/benchmark/*`
  - 扩 case schema、metrics、summary、regression

## 9. 验证要求

### 9.1 一级结果指标

- `task_success_rate`
- `precision_at_k`
- `noise_rate`
- `evidence_insufficient_rate`
- `latency_p95_ms`
- `memory_latency_p95_ms`

### 9.2 长期记忆专用指标

- `ltm_hit_ratio`
- `ltm_effective_hit_rate`
- `ltm_false_help_rate`
- `ltm_stale_hit_rate`
- `ltm_conflict_rate`
- `ltm_cross_session_win_rate`
- `ltm_replay_drift_rate`
- `ltm_latency_overhead_ms`
- `ltm_selected_count`
- `ltm_attributed_success`

### 9.3 反馈闭环专用指标

- `issue_report_submission_rate`
- `issue_report_linked_plan_rate`
- `issue_to_benchmark_case_conversion_rate`
- `issue_reopen_rate`
- `time_to_triage`
- `time_to_fix`
- `post_fix_regression_rate`
- `dev_issue_capture_rate`
- `dev_issue_to_fix_rate`
- `manual_override_rate`

### 9.4 验证门槛

在 `memory-helpful` 子集上，长期记忆应满足：

- `task_success_rate` 高于无长期记忆 baseline
- `precision_at_k` 不显著下降
- `noise_rate` 不显著上升
- `latency_p95_ms` 增长受控
- `ltm_false_help_rate` 与 `ltm_stale_hit_rate` 低于预设阈值

## 10. 主要风险

- 记忆污染：错误 observation 被提升成事实
- 回放失真：缺失 `as_of` 导致结果漂移
- 未来信息泄漏：benchmark 读到未来事实
- 命中增加但质量下降：命中了更多记忆，却让 `precision` 和 `noise` 变差
- 写入膨胀：capture 过多导致 DB 膨胀和分析失真
- 开发反馈泛滥：自动捕获事件过多，淹没真实高价值问题

## 11. 成功判定

本需求整体成功的判定条件是：

1. 长期记忆可以在不破坏现有 memory contract 的前提下接入主链。
2. 用户问题上报和开发内循环反馈都能结构化落盘，并能关联到具体运行。
3. 至少一批真实问题被转为 benchmark case，并用于回归门禁。
4. benchmark 能明确回答长期记忆是“帮了忙”还是“加了噪声”。
5. 开发者能基于问题聚类、严重度、频次和 benchmark 影响快速决定优化优先级。

## 12. 近期建议

建议按以下优先级推进：

1. 先做 `SQLite LongTermMemoryStore + LongTermMemoryProvider + as_of`
2. 再做 `issue_report` 与 `dev_issue/dev_fix` 数据面
3. 再做 `benchmark/summary/regression` 的 LTM 指标扩展
4. 最后做 `triple/edge` 图邻域扩展和更强的自动归因
