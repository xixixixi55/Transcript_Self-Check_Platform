---
name: harness-propose
description: "创建需求变更包并按 Harness 架构约束编排。当用户想要开发新功能、提出新需求、开始新迭代、说'我要做 XX 功能'、'新增 XX'、'propose'时触发。"
---

读取项目根目录对应工具目录下的 `commands/harness/propose.md` 获取详细执行协议，按其步骤执行 `/harness:propose` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 读取 `AGENTS.md` + `harness/iteration-guide.md` + `harness/architecture.md`
2. 扫描活跃变更包，按目标范围关联或确认无匹配
3. 按 `AGENTS.md` 判断 Level；Level 1 直接修改，Level 2 固定创建 tasks.md + 至少一个精简 delta spec 并记录 `workflow_level: 2`，Level 3 创建 proposal + specs + design + tasks
4. 影响分析按架构分层矩阵，tasks 按层级从低到高排序
5. Level 2 不得使用 `Spec impact: N/A`；没有行为 delta 时重新归为 Level 1
6. 展示摘要等待确认

**与 OpenSpec propose 的区别**：
- OpenSpec propose 只管变更包格式和内容质量
- Harness propose 额外注入：分层影响分析、tasks 按架构排序、design 遵循分层约束

完成后提示用户运行 `/harness:apply` 开始开发。
