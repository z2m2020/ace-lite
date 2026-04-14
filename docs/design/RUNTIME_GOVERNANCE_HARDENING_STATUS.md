# Runtime Governance Hardening Status

日期：`2026-04-14`

## 范围
- `subprocess_utils.py` 的 Windows 进程终止路径硬化
- `runtime_stats_store.py` / `stage_artifact_cache_gc.py` 的 SQLite 常量表名治理
- `runtime doctor` / `MCP health` 的 config consistency surface 扩展
- `performance_benchmark.py` 的显式性能回归 gate

## 已完成
- Windows `taskkill` 调用改为先解析绝对路径，解析失败时回退 `proc.kill()`。
- runtime SQL 常量表名现在必须先通过 `_validated_sqlite_identifier()` 校验，再参与 SQL 构造。
- 对 Bandit 无法静态理解、但已被常量表名校验保护的 SQL 构造点，补充了最小 `# nosec B608` 注释。
- `runtime doctor` 顶层新增 `settings_governance`，不再要求消费者深入 `settings.governance` 才能拿到配置一致性摘要。
- `MCP health` 顶层新增 `settings_governance`，并把 `config_warnings` 折叠进 `warnings` / `recommendations`。
- benchmark 层新增 `BenchmarkGateThresholds` / `BenchmarkGateResult` / `evaluate_benchmark_gate()`，可对速度、延迟、内存增量、缓存命中率做显式门禁。

## 三层治理约束
- Layer 1 执行面仍不读取 Layer 2 报告结论反向控制执行逻辑。
- 本轮新增的 `settings_governance` 只做观测和提示，不自动修改 runtime 行为。
- benchmark gate 当前是显式调用型工具，不会在未声明的执行链路里偷偷阻断流程。

## 剩余风险
- `subprocess_utils.py` 仍会保留 `B404/B603` 低风险告警，因为模块职责本身就是受控 subprocess 调用。
- runtime SQL 层仍使用字符串拼接表名，但已限制为编译期常量 + 运行时白名单校验。
- `MCP health` 的 runtime settings governance 使用标准默认路径和无 snapshot 模式，适合作为健康摘要，不保证与某次 CLI `doctor` 调用的 profile/snapshot 完全一致。

## 后续建议
- 如果要把 benchmark gate 接入 CI，下一步应在 benchmark 命令或回归脚本中明确落一个阈值 profile。
- 如果要继续压缩 Bandit 噪音，优先处理 `subprocess_utils.py` 之外的真正中风险项，不建议再为低风险 subprocess 告警做过度重构。
