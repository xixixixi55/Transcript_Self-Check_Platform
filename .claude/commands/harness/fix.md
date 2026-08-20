---
name: "Harness: Fix"
description: "快速修 Bug（Level 1 局部修复直接修改；Level 2 使用 tasks.md + delta spec；Level 3 使用完整变更包）"
argument-hint: "<Bug 描述>"
---

<!-- context-loading: progressive -->

按根目录 `AGENTS.md` 处理 Bug，不以文件数或 change 级别决定本次验证。

1. 搜索活跃 change 的名称和 `tasks.md` 命中；候选范围相关时按需读取 tasks、相关 delta，必要时再读 proposal/design。同能力、结果、调用链或原实现回归继续原包。
2. 没有匹配包时判断 Level：局部恢复既有预期默认 Level 1；正式 Requirement/Scenario 或中等能力变化为 Level 2；重大架构/迁移风险为 Level 3。
3. 渐进式读取：Level 1 只读直接源码/测试；Level 2 再读 tasks/delta；Level 3 只读当前阶段工件。仅在新文件、跨层、公共契约或架构风险时读取 `harness/architecture.md`。
4. 定位根因并最小修复，先复用现有回归证据；覆盖缺口存在时才新增测试。
5. Level 1 跑定向验证；Level 2 跑 `verify:quick`、受影响模块测试、sync 和 scoped strict docs；Level 3 在冻结前定向验证，冻结后统一 Review 与 scoped full gate。
6. 输出关联结论、已读取资料、根因、修改和验证汇总；多个候选仍重叠或需求语义不清时请求用户判定。
