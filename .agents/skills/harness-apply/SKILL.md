---
name: harness-apply
description: "按任务清单开发，遵循 Harness 开发节奏和门控。当用户想要开始开发、执行任务、实现功能、说'开始写代码'、'apply'、'按任务开发'时触发。"
---

完整读取项目工具目录下的 `commands/harness/apply.md` 并执行。只加载当前 task 的 tasks/delta、直接源码和测试；架构、验证、Review 与归档资料在对应风险或阶段出现时再读取。

每个 Task 保留“实现 → 适用检查 → 风险相称验证 → 记录证据”的质量闭环，并遵守失败次数上限。Level 2 完成 sync；Level 3 仅在候选冻结后进入最终 Review/full gate。
