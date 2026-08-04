---
name: harness-apply
description: "按任务清单开发，遵循 Harness 开发节奏和门控。当用户想要开始开发、执行任务、实现功能、说'开始写代码'、'apply'、'按任务开发'时触发。"
---

读取项目根目录对应工具目录下的 `commands/harness/apply.md` 获取详细执行协议，按其步骤执行 `/harness:apply` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 读取变更包 tasks.md + specs/ + design.md
2. 每个 Task 遵循开发节奏：写码 → 架构检查 → 测试 → 验证有效性（→ 可选 Code Review）
3. 硬限制：单步失败 3 次停止，单 Task 验证不超过 10 次
4. Level 2 固定读取 tasks.md + delta spec；收尾按 delta → 实现核对 → sync → living spec 检查，主规格未同步不得正式归档

**与 OpenSpec apply 的区别**：
- OpenSpec apply 只管按 tasks 顺序写代码
- Harness apply 额外注入：5 步开发节奏、门控脚本、测试有效性验证、失败终止条件

完成后提示用户运行 `/harness:verify` + `/harness:review`。
