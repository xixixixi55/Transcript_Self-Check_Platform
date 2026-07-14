---
name: harness-review
description: "三维度验证（完整性+正确性+一致性）代码实现的需求覆盖性。融合 OpenSpec verify spec 验证模型。当用户想要检查需求覆盖、验证 spec 是否实现、说'对照需求检查'、'review'、'spec 验证'、'verify spec'时触发。"
---

读取项目根目录的 `.agents/commands/harness/review.md` 获取详细执行协议，按其步骤执行 `/harness:review` 的完整流程。

**快速参考**（完整步骤见命令文件）：
1. 维度一：完整性 — 任务完成度 + spec 需求覆盖率
2. 维度二：正确性 — 逐条对照 spec 场景，检查代码和测试覆盖
3. 维度三：一致性 — design.md 决策遵循 + Harness 架构约束
4. 生成结构化报告（CRITICAL / WARNING / SUGGESTION）
5. 输出归档建议

**验证模型来源**：
- 完整性 + 正确性 + 一致性三维度：[OpenSpec verify spec](https://github.com/Fission-AI/OpenSpec/blob/main/openspec/specs/opsx-verify-skill/spec.md)
- 架构约束检查：Harness `architecture.md`

**与 `/harness:verify` 的区别**：
- verify = 工程验证（自动化脚本，检查结构正确性）
- review = 需求验证（Agent 三维度审查，检查语义覆盖 + 一致性）

只做审查不修改代码。以 Spec 为仲裁。
