---
name: harness-archive
description: "归档已完成的变更包，含熵治理门控和迭代记录。当用户想要归档、收尾迭代、说'归档'、'archive'、'完成迭代'、'收尾'时触发。"
---

读取项目根目录的 `.codebuddy/commands/harness/archive.md` 获取详细执行协议，按其步骤执行 `/harness:archive` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 运行自动化门控（E-A1 ~ E-A6）
2. Agent 自治检查并修复（E-M1, E-M3, E-M4）
3. 输出分析报告，等待用户确认（E-M2, E-M5）
4. 执行归档（合并 specs + 移入 archive）
5. 创建迭代记录

**与 OpenSpec archive 的区别**：
- OpenSpec archive 只管 specs 合并和文件迁移
- Harness archive 额外注入：自动化门控、Agent 自治检查、人工确认、迭代记录、教训反哺

**MUST NOT**：人工确认项（E-M2, E-M5）未全部确认前不得执行归档。
