---
name: harness-verify
description: "运行工程验证门控（架构检查 + 类型 + 构建 + 测试 + 文档一致性）。当用户想要验证代码、检查是否通过、运行门控、说'跑一下检查'、'verify'、'验证'时触发。"
---

读取项目根目录对应工具目录下的 `commands/harness/verify.md` 获取详细执行协议，按其步骤执行 `/harness:verify` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 运行综合验证（架构检查 + 类型检查 + 构建）
2. 运行自动化测试
3. 运行文档一致性检查
4. Level 2 scoped strict docs 检查 `workflow_level` 与 delta 基本结构；先报告退出码、通过/失败汇总、按类型计数和失败数量，失败后再下钻具体日志

**与 `/harness:review` 的区别**：
- verify = 工程验证（自动化脚本，检查结构正确性）
- review = 需求验证（Agent 对照 spec 场景，检查语义覆盖）

需求 Review 与工程验证按当前级别分别执行；Level 2 不因模块验证再重复运行完整门控，Level 3 收尾使用 `npm run verify:full -- --change <变更包名称>`。
