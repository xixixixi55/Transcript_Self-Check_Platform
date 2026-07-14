---
name: "Harness: Status"
description: "展示当前项目的 Harness 状态（变更包进度、未完成任务、验证结果）"
argument-hint: ""
---

展示当前项目在 Harness 迭代流程中的状态。

---

**步骤**

1. **检查活跃变更包**
   - 扫描 `openspec/changes/` 目录（排除 archive/）
   - 列出每个变更包的名称和状态

2. **展示 Task 进度**
   - 读取活跃变更包的 tasks.md
   - 统计已完成 `[x]` 和未完成 `[ ]` 的 Task 数量

3. **展示上次验证结果**
   - 提示用户可运行 `/harness:verify` 获取最新验证状态

4. **展示可用命令**
   - 根据当前状态推荐下一步操作：
     - 无变更包 → 建议 `/harness:propose`
     - 有未完成 Task → 建议 `/harness:apply` 或 `/harness:continue`
     - Task 全完成 → 建议 `/harness:review` 和 `/harness:archive`

**Output**

```
## Harness Status

**活跃变更包**: <name>
**Task 进度**: N/M 完成
**当前阶段**: ④ 开发中

### 建议下一步
- `/harness:apply` — 继续开发
- `/harness:verify` — 运行工程验证
```
