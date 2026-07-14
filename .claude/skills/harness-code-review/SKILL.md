---
name: harness-code-review
description: "启动独立 Sub-Agent 进行代码审查，实现生成者与评估者分离。当用户想要代码审查、说'review 一下代码'、'code review'、'帮我审查'、'检查代码质量'时触发。"
---

读取项目根目录的 `.claude/commands/harness/code-review.md` 获取详细执行协议，按其步骤执行 `/harness:code-review` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 确定审查范围（Task ID / 文件路径 / 最近完成的 Task）
2. 收集变更文件和上下文
3. 启动独立 Review Sub-Agent（Task 工具，独立上下文）
4. 处理结果：通过 → 继续；驳回 → 修复后重新提交

**与 `/harness:review` 的区别**：
- `code-review` = Task 级别，独立 Sub-Agent，关注代码质量（按 AGENTS.md 级别规则启用）
- `review` = 变更包级别，当前 Agent，关注需求覆盖（全部 Task 完成后）

**核心价值**：开发 Agent 写代码，Review Agent 查代码——消除自审的乐观偏见。
