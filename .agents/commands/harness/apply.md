---
name: "Harness: Apply"
description: "按任务清单开发，遵循 Harness 开发节奏和门控约束"
argument-hint: "[变更包名称]"
---

<!-- context-loading: progressive -->

按任务实施；根目录 `AGENTS.md` 决定级别和验证强度，本命令只补充执行节奏。

## 渐进式上下文

1. 先确定关联 change 和未完成 task，只读取该包的 `tasks.md`、与当前 task 相关的 delta、直接相关源码与现有测试。
2. Level 1 没有 change 工件；Level 2 不因缺少 proposal/design 反向升级，也不读取完整迭代指南。
3. Level 3 只读取与当前实现决策相关的 design/spec，以及 `harness/iteration-guide.md` 的开发章节。
4. 新建文件、跨层引用、公共契约或架构风险出现时读取 `harness/architecture.md`；选择验证、排查失败或准备冻结时再读取 `harness/verification-strategy.md` 的相关章节。

## 每个 Task

1. 核对 delta/设计预期与调用范围，实施最小修改。
2. 运行本次源码变化适用的架构、类型或静态检查；纯文档变化不机械运行源码门控。
3. 先搜索并复用、修改或合并现有验证；仅在风险覆盖缺口存在时新增测试。
4. 运行最小受影响验证。通过只记录汇总；失败才下钻，修复后先重跑失败项。
5. 核心业务、安全、权限、持久化和关键转换应验证断言区分度；低风险展示不强制突变式验证。
6. 证据通过后将必选 task 标为 `[x]`。

连续同类失败 3 次或单 Task 验证循环达到 10 次时停止并报告。发现规格/设计冲突时先更新工件，不凭猜测实现。

## 收尾

- Level 1：定向验证与 diff 检查。
- Level 2：核对 delta 与最终行为，sync living spec，再执行 `verify:quick`、受影响模块测试和 scoped strict docs。
- Level 3：开发与反馈阶段保持定向验证；需求、实现和适用人工验收收敛后冻结候选，再统一 Review 和 scoped full gate。
