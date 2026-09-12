# Harness 稳定先例优先

workflow_level: 2
lifecycle_status: ready-to-archive
spec_sync_status: reconciled
spec_sync_evidence: `openspec/specs/harness-workflow/spec.md` 已同步稳定先例优先合同及三个关键场景

## 关联判断

- 主要候选：`extensible-report-template-platform` 包含触发本次复盘的报告适配反馈，但其正式能力是报告解析，不承载通用开发方法。
- 排除候选：`large-report-preview-liveness` 明确排除 Harness；既有 `harness-workflow-alignment` 与 `harness-change-lifecycle-health` 已归档，不能改写历史。
- 结论：创建独立 Level 2 包，将“项目内稳定先例优先”纳入 `harness-workflow` 正式合同。

## 1. 通用规则

- [x] 1.1 在 `AGENTS.md` 与 `harness/architecture.md` 定义稳定先例优先：新增同类能力前先按用户结果、调用链、输入输出与非功能边界搜索既有稳定实现；默认复用其已验证方法，偏离必须有实质差异证据和拒绝理由。
- [x] 1.2 保持规则单一来源：`AGENTS.md` 只保留入口原则，详细判断集中在 `harness/architecture.md`，不再向其他指南复制正文。

## 2. 工具入口

- [x] 2.1 核对 `.agents/commands/harness/propose.md`、`.agents/commands/harness/apply.md` 及 Skill/Claude 镜像继续以根 `AGENTS.md` 为规则事实源；不在每个入口复制稳定先例正文，避免规则漂移。
- [x] 2.2 复用现有文档一致性与 OpenSpec 门控，不为单条规则新增专用检查器和测试。

## 3. 规格同步与验证

- [x] 3.1 将 delta 同步到 `openspec/specs/harness-workflow/spec.md`，验证新能力、同类格式适配与合理偏离三个场景。
- [x] 3.2 运行 `npm run test:governance`、`npm run verify:quick`、`npm run verify:docs:strict -- --change harness-stable-precedent-first`、OpenSpec strict 与 `git diff --check`。

## 实施证据

- 规则入口：`AGENTS.md`；详细解释：`harness/architecture.md`。
- 工具入口核对：Agent/Claude 的 propose 与 apply 命令均声明根 `AGENTS.md` 为规则入口，Skill 继续转发对应命令，因此不复制规则正文。
- 防回退：复用现有 OpenSpec 规格校验和限定范围严格文档门控，避免为单条原则增加维护成本。
