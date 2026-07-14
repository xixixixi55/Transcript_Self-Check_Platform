---
name: "Harness: Continue"
description: "从中断处恢复开发，自动定位到未完成的 Task 继续执行"
argument-hint: "[变更包名称]"
---

从中断处恢复 Harness 开发流程。

**Input**：可选指定变更包名称。省略时自动推断。

---

**步骤**

1. **定位变更包**
   - 有名称则使用，否则检查活跃变更包
   - 只有一个时自动选择，多个时询问

2. **读取 tasks.md，定位断点**
   - 找到最后一个 `[x]` 标记的 Task
   - 从下一个 `[ ]` Task 开始

3. **展示恢复摘要**
   ```
   恢复变更包: <name>
   已完成: N/M Tasks
   从 Task TXXX 继续
   ```

4. **执行 `/harness:apply` 流程**
   - 从断点 Task 开始，遵循完整的开发节奏
