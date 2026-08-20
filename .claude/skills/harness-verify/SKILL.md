---
name: harness-verify
description: "运行工程验证门控（架构检查 + 类型 + 构建 + 测试 + 文档一致性）。当用户想要验证代码、检查是否通过、运行门控、说'跑一下检查'、'verify'、'验证'时触发。"
---

完整读取项目工具目录下的 `commands/harness/verify.md` 并执行。按当前 Level、修改风险和 change 范围选择门控；只在环境预检、人工验收或失败定位需要时读取验证细则。

先报告汇总，失败后再下钻。Level 2 使用 quick + 受影响验证 + scoped strict docs；Level 3 仅在候选冻结后使用 scoped full gate。
