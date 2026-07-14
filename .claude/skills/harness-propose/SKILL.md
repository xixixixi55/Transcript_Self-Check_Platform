---
name: harness-propose
description: "创建需求变更包并按 Harness 架构约束编排。当用户想要开发新功能、提出新需求、开始新迭代、说'我要做 XX 功能'、'新增 XX'、'propose'时触发。"
---

读取项目根目录的 `.claude/commands/harness/propose.md` 获取详细执行协议，按其步骤执行 `/harness:propose` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 读取 `AGENTS.md` + `harness/iteration-guide.md` + `harness/architecture.md`
2. 创建变更包：proposal + specs + design + tasks
3. 影响分析按架构分层矩阵
4. tasks 按层级从低到高排序
5. 展示摘要等待确认

**与 OpenSpec propose 的区别**：
- OpenSpec propose 只管变更包格式和内容质量
- Harness propose 额外注入：分层影响分析、tasks 按架构排序、design 遵循分层约束

完成后提示用户运行 `/harness:apply` 开始开发。
